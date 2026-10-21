"""Emulated radio link between a ground station and a flight stack in software in the loop.

The relay sits between the ground station (UDP) and the flight stack (TCP serial port of the
software in the loop vehicle). It parses MAVLink frames from both sides and sends them over one
emulated half duplex channel: frames from both directions share one first in first out queue, each
frame occupies the channel for its air time at the profile rate, a frame is lost with the profile's
independent loss probability or when any part of it overlaps a link outage, and command and
acknowledgement frames are retransmitted by an emulated link layer after the retransmission timeout
of linksim/params.csv, as in the mission study. Telemetry frames are not retransmitted.

The security layers of configurations 3 and 4 are emulated by the relay pair: they add bytes on the
air and a vehicle side delay, they do not compute any cryptographic function. Configuration 2 uses
the signing of the flight stack and the ground station, so its 13 B field is real bytes on the link.

The channel logic (Channel) runs on explicit times so that the tests can drive it without sockets.
"""
import collections
import heapq
import random
import select
import socket
import struct
import threading
import time

from . import config as cfgmod

MSG_HEARTBEAT = 0
MSG_COMMAND_LONG = 76
MSG_COMMAND_INT = 75
MSG_COMMAND_ACK = 77
MSG_SET_MODE = 11
MSG_MISSION_COUNT = 44
MSG_MISSION_ITEM = 39
MSG_MISSION_ITEM_INT = 73
MSG_MISSION_REQUEST = 40
MSG_MISSION_REQUEST_INT = 51
MSG_MISSION_ACK = 47

COMMAND_MSGS = {MSG_COMMAND_LONG, MSG_COMMAND_INT, MSG_SET_MODE, MSG_MISSION_COUNT, MSG_MISSION_ITEM,
                MSG_MISSION_ITEM_INT}
ACK_MATCH_S = 0.3
RELIABLE_DOWN = {MSG_COMMAND_ACK, MSG_MISSION_REQUEST, MSG_MISSION_REQUEST_INT, MSG_MISSION_ACK}


# ---------------------------------------------------------------- MAVLink framing

def parse_frames(buf):
    """Split a byte buffer into whole MAVLink 1 or 2 frames.

    Returns (frames, rest) where frames is a list of dicts with keys raw, msgid, seq, sysid, payload
    and rest is the unparsed tail. Bytes before a start marker are skipped.
    """
    frames = []
    i = 0
    n = len(buf)
    while i < n:
        b = buf[i]
        if b == 0xFD:
            if n - i < 10:
                break
            ln = buf[i + 1]
            incompat = buf[i + 2]
            total = 12 + ln + (13 if incompat & 0x01 else 0)
            if n - i < total:
                break
            raw = bytes(buf[i:i + total])
            msgid = raw[7] | (raw[8] << 8) | (raw[9] << 16)
            frames.append(dict(raw=raw, msgid=msgid, seq=raw[4], sysid=raw[5], payload=raw[10:10 + ln],
                               signed=bool(incompat & 0x01)))
            i += total
        elif b == 0xFE:
            if n - i < 6:
                break
            ln = buf[i + 1]
            total = 8 + ln
            if n - i < total:
                break
            raw = bytes(buf[i:i + total])
            frames.append(dict(raw=raw, msgid=raw[5], seq=raw[2], sysid=raw[3], payload=raw[6:6 + ln],
                               signed=False))
            i += total
        else:
            i += 1
    return frames, bytes(buf[i:])


def command_long_id(payload):
    """Command id of a COMMAND_LONG payload (MAVLink 2 trailing zero bytes may be truncated)."""
    p = bytes(payload) + bytes(max(0, 33 - len(payload)))
    return struct.unpack_from('<H', p, 28)[0]


def command_ack_fields(payload):
    """(command, result) of a COMMAND_ACK payload."""
    p = bytes(payload) + bytes(max(0, 10 - len(payload)))
    return struct.unpack_from('<H', p, 0)[0], p[2]


# ---------------------------------------------------------------- channel

class Unit:
    """One unit handed to the channel: a MAVLink frame (possibly with emulated extra bytes) or a handshake flight."""
    __slots__ = ('direction', 'frags', 'reliable', 'meta', 'n_ok', 'failed', 't_submit', 'done', 'n_sent')

    def __init__(self, direction, frags, reliable, meta, t_submit):
        self.direction = direction
        self.frags = list(frags)
        self.reliable = reliable
        self.meta = meta
        self.n_ok = 0
        self.failed = False
        self.done = False
        self.t_submit = t_submit
        self.n_sent = 0


class Channel:
    """Half duplex shared channel with rate, independent frame loss, outages and link layer retransmission."""

    def __init__(self, prof, seed, queue_limit_bytes=None, loss=None):
        self.prof = prof
        self.rate = prof['rate']
        self.loss = prof['loss'] if loss is None else loss
        self.rto = prof['rto']
        self.max_retries = prof['max_retries']
        self.rng = random.Random(seed)
        self.queue = collections.deque()  # (ready_time, unit, frag index, attempt)
        self.retx = []  # heap of (due, counter, unit, idx, attempt)
        self.cur = None
        self.cur_start = 0.0
        self.cur_end = 0.0
        self.outages = []
        self.queue_limit = queue_limit_bytes
        self.queued_bytes = {'up': 0, 'down': 0}
        self._ctr = 0
        self.stats = dict(air_s={'up': 0.0, 'down': 0.0}, wire_bytes={'up': 0, 'down': 0}, frames=0, lost_frames=0,
                          retransmissions=0, failed_units=0, buffer_drops=0, units=0)

    # outages are (start, end) in the channel's time base
    def add_outage(self, start, end):
        self.outages.append((start, end))

    def in_outage(self, t0, t1):
        return any(s < t1 and e > t0 for s, e in self.outages)

    def link_up(self, t):
        return not any(s <= t < e for s, e in self.outages)

    def submit(self, direction, frags, reliable, meta, now):
        """Queue a unit; returns the Unit or None when the radio buffer drops it."""
        size = sum(frags)
        if (not reliable and self.queue_limit is not None
                and self.queued_bytes[direction] + size > self.queue_limit):
            self.stats['buffer_drops'] += 1
            return None
        u = Unit(direction, frags, reliable, meta, now)
        self.stats['units'] += 1
        for i in range(len(frags)):
            self.queue.append((now, u, i, 0))
            self.queued_bytes[direction] += frags[i]
        return u

    def _next_ready(self):
        cands = []
        if self.queue:
            cands.append(self.queue[0][0])
        if self.retx:
            cands.append(self.retx[0][0])
        return min(cands) if cands else None

    def next_event_time(self):
        if self.cur is not None:
            return self.cur_end
        return self._next_ready()

    def _start(self, t):
        # retransmissions that are due go first, then the queue
        if self.retx and self.retx[0][0] <= t:
            due, _, u, i, att = heapq.heappop(self.retx)
            start = max(t, due)
        else:
            rt, u, i, att = self.queue.popleft()
            self.queued_bytes[u.direction] -= u.frags[i]
            start = max(t, rt)
        w = u.frags[i]
        self.cur = (u, i, att)
        self.cur_start = start
        self.cur_end = start + w * 8.0 / self.rate
        self.stats['air_s'][u.direction] += w * 8.0 / self.rate
        self.stats['wire_bytes'][u.direction] += w
        self.stats['frames'] += 1
        if att > 0:
            self.stats['retransmissions'] += 1

    def _complete(self):
        u, i, att = self.cur
        t0, t1 = self.cur_start, self.cur_end
        self.cur = None
        lost = self.in_outage(t0, t1) or (self.rng.random() < self.loss)
        out = []
        if lost:
            self.stats['lost_frames'] += 1
            if u.reliable and att < self.max_retries:
                self._ctr += 1
                heapq.heappush(self.retx, (t1 + self.rto, self._ctr, u, i, att + 1))
            elif not u.failed:
                u.failed = True
                self.stats['failed_units'] += 1
                out.append(('failed', t1, u))
        else:
            u.n_ok += 1
            if u.n_ok == len(u.frags) and not u.failed:
                u.done = True
                out.append(('delivered', t1, u))
        return out

    def advance(self, now):
        """Run the channel up to time now; returns a list of (event, time, unit)."""
        out = []
        while True:
            if self.cur is not None:
                if self.cur_end <= now:
                    t = self.cur_end
                    out += self._complete()
                    nr = self._next_ready()
                    if nr is not None and nr <= now:
                        self._start(max(t, nr))
                    continue
                break
            nr = self._next_ready()
            if nr is not None and nr <= now:
                self._start(nr)
                continue
            break
        return out


# ---------------------------------------------------------------- relay runtime

class Relay(threading.Thread):
    """Relay thread: ground UDP port on one side, flight stack TCP port on the other, channel in between."""

    def __init__(self, prof, sec, seed, gcs_port, vehicle_addr, queue_limit_bytes=None, log=None):
        super().__init__(daemon=True)
        self.prof = prof
        self.sec = sec
        self.seed = seed
        self.chan = Channel(prof, seed, queue_limit_bytes)
        self.lock = threading.RLock()
        self.gcs_port = gcs_port
        self.vehicle_addr = vehicle_addr
        self.gcs_addr = None
        self.running = True
        self.tcp_buf = b''
        self.pending = []  # heap of (time, ctr, side, bytes)
        self._ctr = 0
        self.t0 = time.monotonic()
        self.log = log if log is not None else []
        # stream command records (configuration independent)
        self.stream_cmd_id = None
        self.cmds = []  # dicts in ground send order
        self.vehicle_unacked = collections.deque()
        self.drops = collections.Counter()
        self.frame_counts = collections.Counter()
        # hybrid session state
        self.g_state = 'none'
        self.v_state = 'none'
        self.hs_start = None
        self.hs_times = []
        self.hs_id = 0
        self.last_rx = {'up': None, 'down': None}
        self.teardowns = []
        self.session_events = []
        self.auto_rehandshake = False

    def now(self):
        return time.monotonic()

    # --- control from the runner
    def add_outage(self, start, end):
        with self.lock:
            self.chan.add_outage(start, end)

    def start_session(self):
        with self.lock:
            self._start_handshake(self.now())

    def session_up(self):
        with self.lock:
            return self.g_state == 'up' and self.v_state == 'up'

    def stop(self):
        self.running = False

    # --- handshake (hybrid only)
    def _start_handshake(self, now):
        self.hs_id += 1
        self.g_state = 'hs'
        self.hs_start = now
        self.session_events.append(('hs_start', now, self.hs_id))
        self._send_flight(0, now)

    def _send_flight(self, k, now):
        direction, nbytes, _ = self.sec['flights'][k]
        frags = cfgmod.object_fragments(nbytes, self.prof)
        self.chan.submit(direction, frags, True, dict(kind='hs', k=k, hs=self.hs_id), now)

    def _on_flight(self, u, t):
        k = u.meta['k']
        if u.meta['hs'] != self.hs_id:
            return
        flights = self.sec['flights']
        if flights[k][0] == 'up':
            # vehicle side received flight k
            self.last_rx['up'] = t
            if k == 0:
                self.v_state = 'hs'
            if k == 2:
                self.v_state = 'up'
            if k + 1 < len(flights):
                self._schedule_flight(k + 1, t + flights[k + 1][2])
        else:
            self.last_rx['down'] = t
            if k + 1 < len(flights):
                self._schedule_flight(k + 1, t + flights[k + 1][2])
            else:
                self.g_state = 'up'
                self.hs_times.append((self.hs_id, self.hs_start, t))
                self.session_events.append(('hs_done', t, self.hs_id))

    def _schedule_flight(self, k, t):
        self._ctr += 1
        heapq.heappush(self.pending, (t, self._ctr, 'flight', k))

    def _check_timeouts(self, now):
        if not self.sec.get('session'):
            return
        to = self.sec['timeout_s']
        if self.g_state == 'up' and self.last_rx['down'] is not None and now - self.last_rx['down'] > to:
            self.g_state = 'none'
            self.teardowns.append(('ground', now))
            self.session_events.append(('teardown_ground', now, self.hs_id))
            if self.auto_rehandshake:
                self._start_handshake(now)
        if self.v_state == 'up' and self.last_rx['up'] is not None and now - self.last_rx['up'] > to:
            self.v_state = 'none'
            self.teardowns.append(('vehicle', now))
            self.session_events.append(('teardown_vehicle', now, self.hs_id))

    # --- frames from the two sides
    def _uplink(self, fr, now):
        sec = self.sec
        msgid = fr['msgid']
        self.frame_counts['up_signed' if fr['signed'] else 'up_unsigned'] += 1
        is_cmd = msgid in COMMAND_MSGS
        rec = None
        if msgid == MSG_COMMAND_LONG and command_long_id(fr['payload']) == self.stream_cmd_id:
            rec = dict(idx=len(self.cmds), t_relay_in=now, t_vehicle=None, t_vehicle_ack=None, result=None,
                       t_ground_ack=None, dropped=None, link_up_at_send=self.chan.link_up(now))
            self.cmds.append(rec)
        if sec.get('session') and not (self.g_state == 'up'):
            self.drops['up_no_session'] += 1
            if rec is not None:
                rec['dropped'] = 'no_session'
            return
        n = len(fr['raw']) + sec['tag_bytes']
        if is_cmd and sec['cmd_extra_bytes']:
            frags = cfgmod.object_fragments(n + sec['cmd_extra_bytes'], self.prof)
        else:
            frags = cfgmod.fragments(n, self.prof)
        reliable = msgid != MSG_HEARTBEAT
        u = self.chan.submit('up', frags, reliable, dict(kind='mav', raw=fr['raw'], msgid=msgid, cmd=is_cmd, rec=rec), now)
        if u is None and rec is not None:
            rec['dropped'] = 'buffer'

    def _downlink(self, fr, now):
        sec = self.sec
        msgid = fr['msgid']
        self.frame_counts['down_signed' if fr['signed'] else 'down_unsigned'] += 1
        rec = None
        if msgid == MSG_COMMAND_ACK:
            cmd, result = command_ack_fields(fr['payload'])
            # the flight stack answers within milliseconds; a command delivered longer ago than
            # ACK_MATCH_S without an answer was discarded by the flight stack (for example a signed
            # frame whose timestamp is older than one already accepted)
            while self.vehicle_unacked and now - self.vehicle_unacked[0]['t_vehicle'] > ACK_MATCH_S:
                self.vehicle_unacked.popleft()['dropped'] = 'not_acknowledged_by_vehicle'
            if cmd == self.stream_cmd_id and self.vehicle_unacked:
                rec = self.vehicle_unacked.popleft()
                rec['t_vehicle_ack'] = now
                rec['result'] = result
        if sec.get('session') and not (self.v_state == 'up'):
            self.drops['down_no_session'] += 1
            if rec is not None:
                rec['dropped'] = 'no_session_ack'
            return
        n = len(fr['raw']) + sec['tag_bytes']
        frags = cfgmod.fragments(n, self.prof)
        reliable = msgid in RELIABLE_DOWN
        u = self.chan.submit('down', frags, reliable, dict(kind='mav', raw=fr['raw'], msgid=msgid, cmd=False, rec=rec), now)
        if u is None and rec is not None:
            rec['dropped'] = 'buffer_ack'

    def _deliver(self, ev, t, u):
        m = u.meta
        if ev == 'failed':
            if m['kind'] == 'hs':
                self.session_events.append(('hs_failed', t, m['hs']))
                if self.g_state == 'hs' and m['hs'] == self.hs_id:
                    self._start_handshake(max(t, self.now()))
            elif m.get('rec') is not None and m['rec'].get('dropped') is None:
                m['rec']['dropped'] = 'link_' + u.direction
            return
        if m['kind'] == 'hs':
            self._on_flight(u, t)
            return
        if u.direction == 'up':
            self.last_rx['up'] = t
            delay = self.sec['cmd_delay_s'] if m['cmd'] else 0.0
            self._ctr += 1
            heapq.heappush(self.pending, (t + delay, self._ctr, 'vehicle', m))
        else:
            self.last_rx['down'] = t
            self._ctr += 1
            heapq.heappush(self.pending, (t, self._ctr, 'gcs', m))

    def _flush(self, now, tcp, udp):
        while self.pending and self.pending[0][0] <= now:
            t, _, side, m = heapq.heappop(self.pending)
            if side == 'flight':
                self._send_flight(m, t)
                continue
            if side == 'vehicle':
                if m.get('rec') is not None:
                    m['rec']['t_vehicle'] = now
                    self.vehicle_unacked.append(m['rec'])
                try:
                    tcp.sendall(m['raw'])
                except OSError:
                    pass
            else:
                if m.get('rec') is not None:
                    m['rec']['t_ground_ack'] = now
                if self.gcs_addr is not None:
                    try:
                        udp.sendto(m['raw'], self.gcs_addr)
                    except OSError:
                        pass

    def run(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind(('127.0.0.1', self.gcs_port))
        udp.setblocking(False)
        tcp = socket.create_connection(self.vehicle_addr, timeout=30)
        tcp.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        tcp.setblocking(False)
        self.udp, self.tcp = udp, tcp
        while self.running:
            now = self.now()
            with self.lock:
                for ev, t, u in self.chan.advance(now):
                    self._deliver(ev, t, u)
                self._flush(now, tcp, udp)
                self._check_timeouts(now)
                nxt = [x for x in (self.chan.next_event_time(), self.pending[0][0] if self.pending else None) if x is not None]
            wait = 0.01
            if nxt:
                wait = max(0.0, min(wait, min(nxt) - now))
            r, _, _ = select.select([udp, tcp], [], [], wait)
            now = self.now()
            with self.lock:
                if udp in r:
                    while True:
                        try:
                            data, addr = udp.recvfrom(65535)
                        except BlockingIOError:
                            break
                        self.gcs_addr = addr
                        frs, _ = parse_frames(data)
                        for fr in frs:
                            self._uplink(fr, now)
                if tcp in r:
                    try:
                        data = tcp.recv(65535)
                    except BlockingIOError:
                        data = b''
                    if data:
                        frs, self.tcp_buf = parse_frames(self.tcp_buf + data)
                        for fr in frs:
                            self._downlink(fr, now)
        udp.close()
        tcp.close()
