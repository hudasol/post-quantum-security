"""Relay with an executing gateway pair (round 6): real handshake messages and per message tags on the link.

RESEARCH BENCHMARK GLUE, NOT FOR USE. The ground side gateway sits between the ground station and the emulated
link, the vehicle side gateway between the link and the flight stack. Both run in this process on the host,
call pinned libraries for every cryptographic operation (sitl/gateway.py, sitl/pqcrypto.py) and pass real
bytes over the emulated channel of sitl/linkrelay.py (unchanged). Vehicle side compute is executed on the host
for correctness, and its effect on timing is a delay estimated from RTL simulated cycles: the output of a
vehicle step is released at (input time + RTL delay), so the host speed does not enter the result unless the
host is slower than the delay (counted in host_exceeds). Ground side compute is executed on the host and
enters the timings as host measured (the mission study ignores ground compute).

Streams: link id 0 carries every uplink frame except the ground heartbeat (the frames the link layer
retransmits, commands among them) and is checked under the configured replay rule; link id 1 carries the
heartbeat and is checked under the published rule. Downlink frames are tagged by the vehicle side gateway and
checked by the ground side gateway under the published rule.

Strict rule resynchronisation: the ground side gateway starts a new handshake when its link layer gives up an
uplink frame of stream 0, or when the vehicle side gateway sends a resynchronisation request (16 B,
authenticated with the session key) because a counter above the next one was seen and the next one has not
arrived for the link layer give up span ((max retries + 1) x retransmission timeout); the request is the
8 B counter of the last accepted frame and a 16 B tag over it under the session key. The new handshake resets
both counters.
"""
import collections
import heapq
import time

from . import config as cfgmod
from . import gateway as gw
from . import linkrelay as lr
from . import pqcrypto


class GatewayRelay(lr.Relay):
    def __init__(self, prof, sec, seed, gcs_port, vehicle_addr, queue_limit_bytes=None, log=None):
        super().__init__(prof, sec, seed, gcs_port, vehicle_addr, queue_limit_bytes, log)
        self.design = sec.get('design')
        self.delays = sec.get('delays', {})
        if self.design:
            self.lt_g = gw.LongTerm(self.design)
            self.lt_v = gw.LongTerm(self.design)
        if sec.get('pqsig'):
            self.pq_pk, self.pq_sk = pqcrypto.mldsa44_keypair()
        self.g_keys = {}  # epoch -> dict(key, acc) at the ground
        self.v_keys = {}  # epoch -> dict(key, acc) at the vehicle
        self.g_epoch = 0
        self.v_epoch = 0
        self.v_send_epoch = 0
        self.g_ctr = {0: 0, 1: 0}
        self.v_ctr = {0: 0, 1: 0}
        self.g_hs = None
        self.v_hs = None
        self.hs_reason = None
        self.hs_log = []
        self.rejects = collections.Counter()
        self.down_rejects = collections.Counter()
        self.host = collections.defaultdict(lambda: dict(n=0, host_s=0.0, host_max_s=0.0, exceeds=0, rtl_s=0.0))
        self.arrivals = []
        self.resyncs = []
        self.gap_since = None
        self.rs_sent_at = None
        self.gap_wait = (prof['max_retries'] + 1) * prof['rto']

    # ------------------------------------------------------------ helpers
    def _host(self, op, host_s, rtl_s=None):
        h = self.host[op]
        h['n'] += 1
        h['host_s'] += host_s
        h['host_max_s'] = max(h['host_max_s'], host_s)
        if rtl_s is not None:
            h['rtl_s'] = rtl_s
            if host_s > rtl_s:
                h['exceeds'] += 1

    def _push(self, t, side, m):
        self._ctr += 1
        heapq.heappush(self.pending, (t, self._ctr, side, m))

    def _keys_for_check(self, keys, epoch):
        return [(e, keys[e]) for e in (epoch, epoch - 1) if e in keys]

    # ------------------------------------------------------------ handshake
    def _start_handshake(self, now, reason='initial'):
        self.hs_id += 1
        self.g_state = 'hs'
        self.hs_start = now
        self.hs_reason = reason
        self.session_events.append(('hs_start', now, self.hs_id))
        self.g_hs = gw.GroundHandshake(self.design, self.lt_g, self.lt_v.pk)
        t0 = time.perf_counter()
        f1 = self.g_hs.start()
        self._host('ground_f1', time.perf_counter() - t0)
        self.hs_log.append(dict(hs=self.hs_id, reason=reason, t_start=now, t_done=None, failed=None))
        self._submit_flight(0, f1, now)

    def _submit_flight(self, k, data, now):
        direction = 'up' if k in (0, 2) else 'down'
        frags = cfgmod.object_fragments(len(data), self.prof)
        self.chan.submit(direction, frags, True, dict(kind='hs', k=k, hs=self.hs_id, data=data), now)

    def _on_flight(self, u, t):
        m = u.meta
        if m['hs'] != self.hs_id:
            return
        k, data = m['k'], m['data']
        d = self.design
        if k == 0:
            self.last_rx['up'] = t
            if self.v_state != 'up':
                self.v_state = 'hs'
            self.v_hs = gw.VehicleHandshake(d, self.lt_v, self.lt_g.pk)
            t0 = time.perf_counter()
            f2 = self.v_hs.on_f1(data)
            rtl = self.delays.get(f'{d}_vehicle_f2', 0.0)
            self._host('vehicle_f2', time.perf_counter() - t0, rtl)
            self._push(t + rtl, 'vflight', (1, f2, self.hs_id))
        elif k == 1:
            self.last_rx['down'] = t
            t0 = time.perf_counter()
            f3 = self.g_hs.on_f2(data)
            self._host('ground_f3', time.perf_counter() - t0)
            self._submit_flight(2, f3, t)
        elif k == 2:
            self.last_rx['up'] = t
            t0 = time.perf_counter()
            f4, why = self.v_hs.on_f3(data)
            rtl = self.delays.get(f'{d}_vehicle_f4', 0.0)
            self._host('vehicle_f4', time.perf_counter() - t0, rtl)
            if why is not None:
                self.session_events.append(('hs_rejected_vehicle_' + why, t, self.hs_id))
                return
            self.v_epoch += 1
            self.v_keys[self.v_epoch] = dict(key=self.v_hs.key, acc={0: gw.Acceptor(self.sec['rule'], self.sec['window']),
                                                                    1: gw.Acceptor('published')})
            self.v_keys.pop(self.v_epoch - 2, None)
            self.gap_since = None
            self.rs_sent_at = None
            self._push(t + rtl, 'vflight', (3, f4, self.hs_id))
        else:
            self.last_rx['down'] = t
            t0 = time.perf_counter()
            why = self.g_hs.on_f4(data)
            self._host('ground_accept', time.perf_counter() - t0)
            if why is not None:
                self.session_events.append(('hs_rejected_ground_' + why, t, self.hs_id))
                return
            self.g_epoch += 1
            self.g_keys[self.g_epoch] = dict(key=self.g_hs.key, acc={0: gw.Acceptor('published'), 1: gw.Acceptor('published')})
            self.g_keys.pop(self.g_epoch - 2, None)
            self.g_ctr = {0: 0, 1: 0}
            self.g_state = 'up'
            self.hs_times.append((self.hs_id, self.hs_start, t))
            self.hs_log[-1]['t_done'] = t
            self.session_events.append(('hs_done', t, self.hs_id))

    def _resync(self, t, trigger):
        if self.g_state != 'up':
            return
        self.resyncs.append((t, trigger))
        self.session_events.append(('resync_' + trigger, t, self.hs_id + 1))
        self._start_handshake(t, 'resync_' + trigger)

    def _check_timeouts(self, now):
        """Session timeouts as in the round 5 relay, plus the strict rule gap timer of the vehicle side gateway."""
        if not self.sec.get('session'):
            return
        to = self.sec['timeout_s']
        if self.g_state == 'up' and self.last_rx['down'] is not None and now - self.last_rx['down'] > to:
            self.g_state = 'none'
            self.teardowns.append(('ground', now))
            self.session_events.append(('teardown_ground', now, self.hs_id))
            if self.auto_rehandshake:
                self._start_handshake(now, 'teardown')
        if self.v_state == 'up' and self.last_rx['up'] is not None and now - self.last_rx['up'] > to:
            self.v_state = 'none'
            self.v_keys.clear()
            self.teardowns.append(('vehicle', now))
            self.session_events.append(('teardown_vehicle', now, self.hs_id))
        if self.sec.get('rule') != 'strict' or self.v_state != 'up' or self.v_epoch not in self.v_keys:
            self.gap_since = None
            return
        acc = self.v_keys[self.v_epoch]['acc'][0]
        if not acc.gap():
            self.gap_since = None
            return
        if self.gap_since is None:
            self.gap_since = now
        due = self.rs_sent_at is None or now - self.rs_sent_at > self.gap_wait
        if now - self.gap_since > self.gap_wait and due:
            data = int(acc.hi).to_bytes(8, 'little', signed=True) + gw.resync_request(self.v_keys[self.v_epoch]['key'], acc.hi)
            self.chan.submit('down', cfgmod.fragments(len(data), self.prof), True, dict(kind='rs', data=data), now)
            self.rs_sent_at = now
            self.session_events.append(('resync_request_sent', now, self.hs_id))

    # ------------------------------------------------------------ frames from the ground station
    def _uplink(self, fr, now):
        sec = self.sec
        msgid = fr['msgid']
        raw = fr['raw']
        self.frame_counts['up_signed' if fr['signed'] else 'up_unsigned'] += 1
        is_cmd = msgid in lr.COMMAND_MSGS
        rec = None
        if msgid == lr.MSG_COMMAND_LONG and lr.command_long_id(fr['payload']) == self.stream_cmd_id:
            rec = dict(idx=len(self.cmds), t_relay_in=now, t_vehicle=None, t_vehicle_ack=None, result=None,
                       t_ground_ack=None, dropped=None, link_up_at_send=self.chan.link_up(now), counter=None,
                       t_gateway=None, epoch=None)
            self.cmds.append(rec)
        meta = dict(kind='mav', raw=raw, msgid=msgid, cmd=is_cmd, rec=rec)
        reliable = msgid != lr.MSG_HEARTBEAT
        if sec.get('session'):
            if self.g_state != 'up':
                self.drops['up_no_session_' + (self.hs_reason or 'none')] += 1
                if rec is not None:
                    rec['dropped'] = 'no_session'
                return
            stream = 0 if reliable else 1
            c = self.g_ctr[stream]
            self.g_ctr[stream] += 1
            t0 = time.perf_counter()
            field = gw.tag_field(self.g_keys[self.g_epoch]['key'], raw, stream, c)
            self._host('ground_tag', time.perf_counter() - t0)
            data = raw + field
            meta.update(data=data, stream=stream, counter=c, epoch=self.g_epoch)
            if rec is not None:
                rec['counter'] = c
                rec['epoch'] = self.g_epoch
            frags = cfgmod.fragments(len(data), self.prof)
        elif sec.get('pqsig') and is_cmd:
            t0 = time.perf_counter()
            sig = pqcrypto.mldsa44_sign(raw, self.pq_sk)
            self._host('ground_sign_command', time.perf_counter() - t0)
            meta.update(data=raw + sig)
            frags = cfgmod.object_fragments(len(raw) + len(sig), self.prof)
        else:
            meta.update(data=raw)
            frags = cfgmod.fragments(len(raw), self.prof)
        u = self.chan.submit('up', frags, reliable, meta, now)
        if u is None and rec is not None:
            rec['dropped'] = 'buffer'

    # ------------------------------------------------------------ frames from the flight stack
    def _downlink(self, fr, now):
        sec = self.sec
        msgid = fr['msgid']
        raw = fr['raw']
        self.frame_counts['down_signed' if fr['signed'] else 'down_unsigned'] += 1
        rec = None
        if msgid == lr.MSG_COMMAND_ACK:
            cmd, result = lr.command_ack_fields(fr['payload'])
            while self.vehicle_unacked and now - self.vehicle_unacked[0]['t_vehicle'] > lr.ACK_MATCH_S:
                self.vehicle_unacked.popleft()['dropped'] = 'not_acknowledged_by_vehicle'
            if cmd == self.stream_cmd_id and self.vehicle_unacked:
                rec = self.vehicle_unacked.popleft()
                rec['t_vehicle_ack'] = now
                rec['result'] = result
        reliable = msgid in lr.RELIABLE_DOWN
        meta = dict(kind='mav', raw=raw, msgid=msgid, cmd=False, rec=rec)
        ready = now
        if sec.get('session'):
            if self.v_state != 'up' or self.v_send_epoch not in self.v_keys:
                self.drops['down_no_session'] += 1
                if rec is not None:
                    rec['dropped'] = 'no_session_ack'
                return
            stream = 0 if reliable else 1
            c = self.v_ctr[stream]
            self.v_ctr[stream] += 1
            t0 = time.perf_counter()
            field = gw.tag_field(self.v_keys[self.v_send_epoch]['key'], raw, stream, c)
            rtl = self.delays.get('tag_make', 0.0)
            self._host('vehicle_tag', time.perf_counter() - t0, rtl)
            meta.update(data=raw + field, stream=stream, counter=c)
            ready = now + rtl
        else:
            meta.update(data=raw)
        u = self.chan.submit('down', cfgmod.fragments(len(meta['data']), self.prof), reliable, meta, ready)
        if u is None and rec is not None:
            rec['dropped'] = 'buffer_ack'

    # ------------------------------------------------------------ deliveries from the channel
    def _deliver(self, ev, t, u):
        m = u.meta
        if ev == 'failed':
            if m['kind'] == 'hs':
                self.session_events.append(('hs_failed', t, m['hs']))
                if self.hs_log and self.hs_log[-1]['hs'] == m['hs']:
                    self.hs_log[-1]['failed'] = t
                if self.g_state == 'hs' and m['hs'] == self.hs_id:
                    self._start_handshake(max(t, self.now()), 'retry_after_give_up')
            elif m['kind'] == 'rs':
                self.rs_sent_at = None
            else:
                if m.get('rec') is not None and m['rec'].get('dropped') is None:
                    m['rec']['dropped'] = 'link_' + u.direction
                if (u.direction == 'up' and self.sec.get('rule') == 'strict' and m.get('stream') == 0
                        and m.get('epoch') == self.g_epoch):
                    self._resync(t, 'ground_give_up')
            return
        if m['kind'] == 'hs':
            self._on_flight(u, t)
            return
        if m['kind'] == 'rs':
            self._on_resync_request(m, t)
            return
        if u.direction == 'up':
            self._vehicle_in(m, t)
        else:
            self._ground_in(m, t)

    def _on_resync_request(self, m, t):
        c = int.from_bytes(m['data'][:8], 'little', signed=True)
        for e, k in self._keys_for_check(self.g_keys, self.g_epoch):
            if gw.resync_request(k['key'], c) == m['data'][8:]:
                self.last_rx['down'] = t
                self._resync(t, 'vehicle_request')
                return
        self.down_rejects['bad_resync_request'] += 1

    def _vehicle_in(self, m, t):
        sec = self.sec
        rec = m.get('rec')
        if rec is not None:
            rec['t_gateway'] = t
        delay = 0.0
        if sec.get('session'):
            if self.v_epoch not in self.v_keys:
                self.rejects['no_session_vehicle'] += 1
                if rec is not None:
                    rec['dropped'] = 'no_session_vehicle'
                return
            data = m['data']
            frame, field = data[:-gw.TAG_FIELD_BYTES], data[-gw.TAG_FIELD_BYTES:]
            t0 = time.perf_counter()
            hit = None
            for e, k in self._keys_for_check(self.v_keys, self.v_epoch):
                ok, lid, c = gw.check_field(k['key'], frame, field)
                if ok:
                    hit = (e, k, lid, c)
                    break
            rtl = self.delays.get('tag_check', 0.0)
            self._host('vehicle_tag_check', time.perf_counter() - t0, rtl)
            if hit is None:
                self.rejects['bad_tag'] += 1
                if rec is not None:
                    rec['dropped'] = 'rejected_bad_tag'
                return
            e, k, lid, c = hit
            self.last_rx['up'] = t
            accepted, why = k['acc'][lid].accept(c)
            if lid == 0:
                self.arrivals.append((t, e, c, int(accepted), why or '', m['msgid']))
            if not accepted:
                self.rejects[f'stream{lid}_{why}'] += 1
                if rec is not None:
                    rec['dropped'] = 'rejected_' + why
                return
            delay = rtl
            frame_out = frame
        elif sec.get('pqsig') and m['cmd']:
            data = m['data']
            frame, sig = data[:-pqcrypto.MLDSA44_SIG], data[-pqcrypto.MLDSA44_SIG:]
            t0 = time.perf_counter()
            ok = pqcrypto.mldsa44_verify(sig, frame, self.pq_pk)
            rtl = self.delays.get('mldsa44_verify_command', 0.0)
            self._host('vehicle_verify_command', time.perf_counter() - t0, rtl)
            if not ok:
                self.rejects['bad_signature'] += 1
                if rec is not None:
                    rec['dropped'] = 'rejected_bad_signature'
                return
            delay = rtl
            frame_out = frame
        else:
            self.last_rx['up'] = t
            frame_out = m['raw']
        out = dict(m, raw=frame_out)
        self._push(t + delay, 'vehicle', out)

    def _ground_in(self, m, t):
        if self.sec.get('session'):
            data = m['data']
            frame, field = data[:-gw.TAG_FIELD_BYTES], data[-gw.TAG_FIELD_BYTES:]
            t0 = time.perf_counter()
            hit = None
            for e, k in self._keys_for_check(self.g_keys, self.g_epoch):
                ok, lid, c = gw.check_field(k['key'], frame, field)
                if ok:
                    hit = (k, lid, c)
                    break
            self._host('ground_tag_check', time.perf_counter() - t0)
            rec = m.get('rec')
            if hit is None:
                self.down_rejects['bad_or_unknown_key'] += 1
                if rec is not None:
                    rec['dropped'] = 'ack_rejected_tag'
                return
            k, lid, c = hit
            accepted, why = k['acc'][lid].accept(c)
            if not accepted:
                self.down_rejects[f'stream{lid}_{why}'] += 1
                if rec is not None:
                    rec['dropped'] = 'ack_rejected_' + why
                return
            self.last_rx['down'] = t
            m = dict(m, raw=frame)
        else:
            self.last_rx['down'] = t
        self._push(t, 'gcs', m)

    def _flush(self, now, tcp, udp):
        while self.pending and self.pending[0][0] <= now:
            t, _, side, m = heapq.heappop(self.pending)
            if side == 'vflight':
                k, data, hs = m
                if hs != self.hs_id:
                    continue
                if k == 3:
                    # the vehicle tags the downlink with the new key from the moment it sends F4
                    self.v_send_epoch = self.v_epoch
                    self.v_ctr = {0: 0, 1: 0}
                    self.v_state = 'up'
                self._submit_flight(k, data, t)
                continue
            if side == 'vehicle':
                if m.get('rec') is not None:
                    m['rec']['t_vehicle'] = now
                    self.vehicle_unacked.append(m['rec'])
                try:
                    tcp.sendall(m['raw'])
                except OSError:
                    pass
            elif side == 'gcs':
                if m.get('rec') is not None:
                    m['rec']['t_ground_ack'] = now
                if self.gcs_addr is not None:
                    try:
                        udp.sendto(m['raw'], self.gcs_addr)
                    except OSError:
                        pass

    def gateway_stats(self):
        return dict(rejects=dict(self.rejects), down_rejects=dict(self.down_rejects),
                    host=dict(self.host), resyncs=[list(x) for x in self.resyncs], handshakes=self.hs_log,
                    gap_wait_s=self.gap_wait, delays_s=self.delays)
