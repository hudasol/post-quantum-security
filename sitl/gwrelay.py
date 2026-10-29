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

Design K (kem_auth, three flights, no signatures): the vehicle side gateway answers F1 with F2 after the delay of
its F2 step; the ground side gateway checks the vehicle tag in F2, accepts (it tags the uplink from then on) and
sends F3; the vehicle side gateway checks F3 and accepts after the delay of its accept step (it tags the downlink
from then on). The handshake is complete, and its time is recorded, when the vehicle side gateway accepts (both
sides then hold the key), which is the point of the hybrid design where the ground accepts F4. A link layer give
up of F3 makes the ground side gateway start a new handshake, as a give up of any flight does in the hybrid design.

Strict rule resynchronisation: the ground side gateway starts a new handshake when its link layer gives up an
uplink frame of stream 0, or when the vehicle side gateway sends a resynchronisation request (16 B,
authenticated with the session key) because a counter above the next one was seen and the next one has not
arrived for the link layer give up span ((max retries + 1) x retransmission timeout); the request is the
8 B counter of the last accepted frame and a 16 B tag over it under the session key. The new handshake resets
both counters.

In band resynchronisation (hybrid_strict_inband, the strict rule without a new handshake): the same two triggers
start a resynchronisation inside the current session with one authenticated message each way under the current
session key. After a vehicle request (24 B, as above) the ground side gateway answers with a 24 B set message that
carries the next counter (the lowest counter of link id 0 still in flight, or the next one to be sent) and a 16 B
tag; after a link layer give up of a link id 0 frame the ground side gateway sends the set message itself and the
vehicle side gateway answers with a 24 B acknowledgement (the ground repeats an unacknowledged set message after
the give up span). The vehicle side gateway moves its next expected counter forward to the counter of a valid set
message and never back, then both sides continue with the same key. Vehicle side compute for these messages is the
tag check delay (set message) and the tag delay (request and acknowledgement). A teardown after an outage longer
than the session timeout still forces a new handshake.

ML-DSA-44 per command with a counter (pqsig_counter): the ground side gateway signs each command frame with a 6 B
counter appended; the vehicle side gateway verifies the signature over frame and counter and accepts the counter
under the published rule (greater than the last accepted one, gaps allowed); a replayed command is rejected.
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
        self.pq_counter = bool(sec.get('pq_counter'))
        self.pq_ctr = 0
        self.pq_acc = gw.Acceptor('published')
        self.inband = bool(sec.get('inband'))
        self.g_inflight = set()  # counters of link id 0 frames of the current ground key still in flight (in band)
        self.g_set_out = None  # unacknowledged set message of the ground side gateway (in band)
        self.g_set_again = False
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

    def session_up(self):
        """Both sides hold the key of the current handshake. For design K the ground accepts first (on F2), and
        the vehicle side gateway may still be up with the previous key, so the current handshake must also be
        complete at the vehicle (recorded in hs_times when it accepts F3)."""
        with self.lock:
            up = self.g_state == 'up' and self.v_state == 'up'
            if self.design == 'kem_auth':
                up = up and bool(self.hs_times) and self.hs_times[-1][0] == self.hs_id
            return up

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
        if self.design == 'kem_auth':
            self.g_hs = gw.KemAuthGround(self.lt_g, self.lt_v.pk)
        else:
            self.g_hs = gw.GroundHandshake(self.design, self.lt_g, self.lt_v.pk)
        t0 = time.perf_counter()
        f1 = self.g_hs.start()
        self._host('ground_f1', time.perf_counter() - t0)
        self.hs_log.append(dict(hs=self.hs_id, reason=reason, t_start=now, t_done=None, failed=None))
        if self.design == 'kem_auth':
            self.hs_log[-1]['t_ground_accept'] = None
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
        if d == 'kem_auth':
            self._on_flight_kem_auth(k, data, t)
            return
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
            self._inband_reset()
            self.g_state = 'up'
            self.hs_times.append((self.hs_id, self.hs_start, t))
            self.hs_log[-1]['t_done'] = t
            self.session_events.append(('hs_done', t, self.hs_id))

    def _on_flight_kem_auth(self, k, data, t):
        """Design K: F1 at the vehicle, F2 at the ground (the ground accepts), F3 at the vehicle (it accepts)."""
        if k == 0:
            self.last_rx['up'] = t
            if self.v_state != 'up':
                self.v_state = 'hs'
            self.v_hs = gw.KemAuthVehicle(self.lt_v, self.lt_g.pk)
            t0 = time.perf_counter()
            f2 = self.v_hs.on_f1(data)
            rtl = self.delays.get('kem_auth_vehicle_f2', 0.0)
            self._host('vehicle_f2', time.perf_counter() - t0, rtl)
            self._push(t + rtl, 'vflight', (1, f2, self.hs_id))
        elif k == 1:
            self.last_rx['down'] = t
            t0 = time.perf_counter()
            f3, why = self.g_hs.on_f2(data)
            self._host('ground_f3', time.perf_counter() - t0)
            if why is not None:
                self.session_events.append(('hs_rejected_ground_' + why, t, self.hs_id))
                return
            self.g_epoch += 1
            self.g_keys[self.g_epoch] = dict(key=self.g_hs.key, acc={0: gw.Acceptor('published'), 1: gw.Acceptor('published')})
            self.g_keys.pop(self.g_epoch - 2, None)
            self.g_ctr = {0: 0, 1: 0}
            self._inband_reset()
            self.g_state = 'up'
            self.hs_log[-1]['t_ground_accept'] = t
            self.session_events.append(('hs_ground_accepted', t, self.hs_id))
            self._submit_flight(2, f3, t)
        elif k == 2:
            self.last_rx['up'] = t
            t0 = time.perf_counter()
            why = self.v_hs.on_f3(data)
            rtl = self.delays.get('kem_auth_vehicle_accept', 0.0)
            self._host('vehicle_accept', time.perf_counter() - t0, rtl)
            if why is not None:
                self.session_events.append(('hs_rejected_vehicle_' + why, t, self.hs_id))
                return
            self.v_epoch += 1
            self.v_keys[self.v_epoch] = dict(key=self.v_hs.key, acc={0: gw.Acceptor(self.sec['rule'], self.sec['window']),
                                                                    1: gw.Acceptor('published')})
            self.v_keys.pop(self.v_epoch - 2, None)
            self.gap_since = None
            self.rs_sent_at = None
            self._push(t + rtl, 'vflight', ('accept', None, self.hs_id))

    def _inband_reset(self):
        self.g_inflight = set()
        self.g_set_out = None
        self.g_set_again = False

    def _resync(self, t, trigger):
        if self.g_state != 'up':
            return
        if self.inband:
            self._resync_inband(t, trigger)
            return
        self.resyncs.append((t, trigger))
        self.session_events.append(('resync_' + trigger, t, self.hs_id + 1))
        self._start_handshake(t, 'resync_' + trigger)

    # ------------------------------------------------------------ in band resynchronisation
    def _resync_inband(self, t, trigger):
        """Resynchronise the counter of link id 0 inside the current session (no new handshake)."""
        if trigger == 'ground_give_up' and self.g_set_out is not None:
            # a set message is already on its way; send another one once it is acknowledged
            self.g_set_again = True
            return
        self.resyncs.append((t, trigger))
        self.session_events.append(('resync_inband_' + trigger, t, self.hs_id))
        self._send_set(t, solicited=trigger == 'vehicle_request')

    def _send_set(self, t, solicited):
        c = min(self.g_inflight) if self.g_inflight else self.g_ctr[0]
        t0 = time.perf_counter()
        data = gw.resync_set(self.g_keys[self.g_epoch]['key'], c)
        self._host('ground_resync_tag', time.perf_counter() - t0)
        self.chan.submit('up', cfgmod.fragments(len(data), self.prof), True,
                         dict(kind='rset', data=data, epoch=self.g_epoch, solicited=solicited), t)
        self.session_events.append(('resync_set_sent', t, self.hs_id))
        if not solicited:
            self.g_set_out = dict(t=t, c=c, epoch=self.g_epoch, t_delivered=None)

    def _vehicle_set(self, m, t):
        """Set message at the vehicle side gateway: check the tag, then apply after the tag check delay."""
        if m.get('epoch') == self.g_epoch and self.g_set_out is not None and not m.get('solicited'):
            self.g_set_out['t_delivered'] = t  # the ground link layer learns that the set message arrived
        if self.v_epoch not in self.v_keys:
            self.rejects['resync_set_no_session_vehicle'] += 1
            return
        t0 = time.perf_counter()
        hit = None
        for e, k in self._keys_for_check(self.v_keys, self.v_epoch):
            c = gw.open_resync(k['key'], 'set', m['data'])
            if c is not None:
                hit = (e, c)
                break
        rtl = self.delays.get('tag_check', 0.0)
        self._host('vehicle_resync_check', time.perf_counter() - t0, rtl)
        if hit is None:
            self.rejects['bad_resync_set'] += 1
            return
        self.last_rx['up'] = t
        self._push(t + rtl, 'vresync', hit)

    def _vehicle_apply_set(self, e, c, t):
        if e not in self.v_keys:
            return
        acc = self.v_keys[e]['acc'][0]
        moved = acc.set_next(c)
        self.session_events.append(('resync_inband_' + ('applied' if moved else 'no_change'), t, self.hs_id))
        self.gap_since = None
        if self.rs_sent_at is not None:
            # the answer to the request of this gateway: one message each way, no acknowledgement
            self.rs_sent_at = None
            return
        t0 = time.perf_counter()
        data = gw.resync_ack(self.v_keys[e]['key'], c)
        rtl = self.delays.get('tag_make', 0.0)
        self._host('vehicle_resync_tag', time.perf_counter() - t0, rtl)
        self.chan.submit('down', cfgmod.fragments(len(data), self.prof), True, dict(kind='rack', data=data), t + rtl)

    def _ground_ack(self, m, t):
        t0 = time.perf_counter()
        c = None
        for e, k in self._keys_for_check(self.g_keys, self.g_epoch):
            c = gw.open_resync(k['key'], 'ack', m['data'])
            if c is not None:
                break
        self._host('ground_resync_check', time.perf_counter() - t0)
        if c is None:
            self.down_rejects['bad_resync_ack'] += 1
            return
        self.last_rx['down'] = t
        if self.g_set_out is not None and c == self.g_set_out['c']:
            self.g_set_out = None
            self.session_events.append(('resync_inband_acknowledged', t, self.hs_id))
            if self.g_set_again and self.g_state == 'up':
                self.g_set_again = False
                self._resync_inband(t, 'ground_give_up')

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
        if (self.inband and self.g_set_out is not None and self.g_state == 'up'
                and self.g_set_out['epoch'] == self.g_epoch and self.g_set_out['t_delivered'] is not None
                and now - self.g_set_out['t_delivered'] > self.gap_wait):
            # delivered but not acknowledged within the give up span: send the set message again (same
            # resynchronisation); a set message given up by the link layer is sent again at once (_deliver)
            self._send_set(now, solicited=False)
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
            ready = now
            if self.inband:
                t0 = time.perf_counter()
                data = gw.resync_request_msg(self.v_keys[self.v_epoch]['key'], acc.hi)
                rtl = self.delays.get('tag_make', 0.0)
                self._host('vehicle_resync_tag', time.perf_counter() - t0, rtl)
                ready = now + rtl
            else:
                data = int(acc.hi).to_bytes(8, 'little', signed=True) + gw.resync_request(self.v_keys[self.v_epoch]['key'], acc.hi)
            self.chan.submit('down', cfgmod.fragments(len(data), self.prof), True, dict(kind='rs', data=data), ready)
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
        elif sec.get('pqsig') and is_cmd and self.pq_counter:
            c = self.pq_ctr
            self.pq_ctr += 1
            t0 = time.perf_counter()
            data = gw.pqsig_counter_seal(raw, c, self.pq_sk)
            self._host('ground_sign_command', time.perf_counter() - t0)
            meta.update(data=data, counter=c)
            if rec is not None:
                rec['counter'] = c
            frags = cfgmod.object_fragments(len(data), self.prof)
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
        if u is not None and self.inband and meta.get('stream') == 0:
            self.g_inflight.add(meta['counter'])
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
        if self.inband and m['kind'] == 'mav' and u.direction == 'up' and m.get('epoch') == self.g_epoch:
            self.g_inflight.discard(m.get('counter'))
        if ev == 'failed':
            if m['kind'] == 'hs':
                self.session_events.append(('hs_failed', t, m['hs']))
                if self.hs_log and self.hs_log[-1]['hs'] == m['hs']:
                    self.hs_log[-1]['failed'] = t
                if self.g_state == 'hs' and m['hs'] == self.hs_id:
                    self._start_handshake(max(t, self.now()), 'retry_after_give_up')
                elif self.design == 'kem_auth' and m['k'] == 2 and m['hs'] == self.hs_id:
                    # the ground had accepted, but F3 never reached the vehicle
                    self._start_handshake(max(t, self.now()), 'retry_after_give_up')
            elif m['kind'] == 'rs':
                self.rs_sent_at = None
            elif m['kind'] == 'rset':
                if (not m['solicited'] and self.g_set_out is not None and self.g_state == 'up'
                        and m['epoch'] == self.g_epoch):
                    self._send_set(t, solicited=False)
            elif m['kind'] == 'rack':
                pass  # the ground side gateway repeats its set message after the give up span
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
        if m['kind'] == 'rset':
            self._vehicle_set(m, t)
            return
        if m['kind'] == 'rack':
            self._ground_ack(m, t)
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
        elif sec.get('pqsig') and m['cmd'] and self.pq_counter:
            t0 = time.perf_counter()
            ok, frame, c = gw.pqsig_counter_open(m['data'], self.pq_pk)
            rtl = self.delays.get('mldsa44_verify_command', 0.0)
            self._host('vehicle_verify_command', time.perf_counter() - t0, rtl)
            if not ok:
                self.rejects['bad_signature'] += 1
                if rec is not None:
                    rec['dropped'] = 'rejected_bad_signature'
                return
            accepted, why = self.pq_acc.accept(c)
            self.arrivals.append((t, 0, c, int(accepted), why or '', m['msgid']))
            if not accepted:
                self.rejects[f'counter_{why}'] += 1
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
                if k == 'accept':
                    # design K: the vehicle accepts F3 and tags the downlink with the new key from now on
                    self.v_send_epoch = self.v_epoch
                    self.v_ctr = {0: 0, 1: 0}
                    self.v_state = 'up'
                    self.hs_times.append((self.hs_id, self.hs_start, t))
                    self.hs_log[-1]['t_done'] = t
                    self.session_events.append(('hs_done', t, self.hs_id))
                    continue
                if k == 3:
                    # the vehicle tags the downlink with the new key from the moment it sends F4
                    self.v_send_epoch = self.v_epoch
                    self.v_ctr = {0: 0, 1: 0}
                    self.v_state = 'up'
                self._submit_flight(k, data, t)
                continue
            if side == 'vresync':
                self._vehicle_apply_set(m[0], m[1], t)
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
