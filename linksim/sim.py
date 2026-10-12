"""Seeded event simulation of fragment delivery over a half duplex link.

Author: Huda Mueen.

Only sizes and times are simulated. Messages are byte counts. No
cryptographic operation is performed. All results are estimated from
published sizes, not measured.

Modelling choices (all labelled as ASSUMPTION in params.csv or README):
* Independent Bernoulli loss with the same probability for data and acks.
* Each side has its own duty cycle budget (silence after a transmission of
  air * (1/duty - 1)).
* The retransmission timeout includes the peer hold off caused by its duty
  cycle, so a late ack is never mistaken for a lost one.
* One turnaround delay per acknowledgement leg, applied at the receiver.
"""
import random
from dataclasses import dataclass, field

from . import model


@dataclass
class Stats:
    wall_s: float = 0.0
    data_air_s: float = 0.0
    ack_air_s: float = 0.0
    duty_wait_s: float = 0.0
    data_frames_sent: int = 0
    ack_frames_sent: int = 0
    unique_frames: int = 0
    payload_bytes: int = 0
    wire_bytes_sent: int = 0
    completed: bool = True
    flights: list = field(default_factory=list)

    @property
    def retransmissions(self):
        return self.data_frames_sent - self.unique_frames

    @property
    def air_s(self):
        return self.data_air_s + self.ack_air_s


class Radio:
    """Half duplex channel with a duty cycle budget per transmitter."""

    def __init__(self, link, stats):
        self.link = link
        self.stats = stats
        self.free = {"A": 0.0, "B": 0.0}

    def send(self, who, t_ready, wire_bytes, kind="data"):
        start = max(t_ready, self.free[who])
        air = self.link.air_s(wire_bytes)
        end = start + air
        self.free[who] = end + self.link.off_s(air)
        st = self.stats
        st.duty_wait_s += start - t_ready
        st.wire_bytes_sent += wire_bytes
        if kind == "data":
            st.data_air_s += air
            st.data_frames_sent += 1
        else:
            st.ack_air_s += air
            st.ack_frames_sent += 1
        return start, end

    def rto(self, receiver, tx_end, p, ack_wire):
        td = self.link.turnaround_s
        hold = max(0.0, self.free[receiver] - (tx_end + td))
        return p["rto_factor"] * (td + self.link.air_s(ack_wire) + hold)


def _ack_wire(link, p, bitmap_frames):
    bitmap = -(-bitmap_frames // 8) if bitmap_frames else 0
    return link.wire_bytes(int(p["ack_payload_bytes"]) + bitmap)


def stop_and_wait(radio, rng, loss, snd, rcv, sizes, p, t):
    """Send each fragment, wait for its ack, resend on timeout."""
    link = radio.link
    max_try = int(p["max_retries"]) + 1
    ack_wire = _ack_wire(link, p, 0)
    for w in sizes:
        tries = 0
        while True:
            tries += 1
            if tries > max_try:
                return t, False
            _, e = radio.send(snd, t, w)
            ack_ok = False
            re = e
            if rng.random() >= loss:  # data arrived
                rto = radio.rto(rcv, e, p, ack_wire)
                _, re = radio.send(rcv, e + link.turnaround_s, ack_wire, "ack")
                ack_ok = rng.random() >= loss
            else:
                rto = radio.rto(rcv, e, p, ack_wire)
            if ack_ok:
                t = re
                break
            t = e + rto
    return t, True


def selective_repeat(radio, rng, loss, snd, rcv, sizes, p, t):
    """Window of W fragments, block ack bitmap, poll by resending the last."""
    link = radio.link
    n = len(sizes)
    W = int(p["sr_window_frames"])
    max_try = int(p["max_retries"]) + 1
    ack_wire = _ack_wire(link, p, W)
    has = [False] * n
    acked = [False] * n
    attempts = [0] * n
    pending = list(range(n))
    while pending:
        window = pending[:W]
        arrived = False
        last = window[-1]
        for idx in window:
            attempts[idx] += 1
            if attempts[idx] > max_try:
                return t, False
            _, t = radio.send(snd, t, sizes[idx])
            arrived = rng.random() >= loss
            if arrived:
                has[idx] = True
        polls = 0
        while True:
            e = t
            rto = radio.rto(rcv, e, p, ack_wire)
            if arrived:
                _, re = radio.send(rcv, e + link.turnaround_s, ack_wire, "ack")
                if rng.random() >= loss:
                    t = re
                    for idx in window:
                        if has[idx]:
                            acked[idx] = True
                    break
            t = e + rto
            polls += 1
            if polls > int(p["max_retries"]):
                return t, False
            attempts[last] += 1
            _, t = radio.send(snd, t, sizes[last])
            arrived = rng.random() >= loss
            if arrived:
                has[last] = True
        pending = [i for i in pending if not acked[i]]
    return t, True


PROTOS = {"sw": stop_and_wait, "sr": selective_repeat}


def _run_flights(link, flights, proto, loss, seed, p):
    rng = random.Random(seed)
    st = Stats()
    radio = Radio(link, st)
    t = 0.0
    for sender, label, nbytes in flights:
        rcv = "B" if sender == "A" else "A"
        sizes = model.fragment_wire_sizes(link, nbytes)
        t0 = t
        t, ok = PROTOS[proto](radio, rng, loss, sender, rcv, sizes, p, t)
        st.unique_frames += len(sizes)
        st.payload_bytes += nbytes
        st.flights.append((label, nbytes, len(sizes), t - t0))
        if not ok:
            st.completed = False
            break
    st.wall_s = t
    return st


def run_handshake(link_key, variant="hybrid", proto="sr", loss=0.0, seed=1,
                  p=None, signed=False, ecc=False):
    p = p or model.load_params()
    link = model.build_links(p, signed, ecc)[link_key]
    flights = model.handshake_flights(p, variant)
    return _run_flights(link, flights, proto, loss, seed, p)


def run_firmware(link_key, nbytes, proto="sr", loss=0.0, seed=1, p=None,
                 signed=False, ecc=False):
    """Firmware of nbytes from ground (A) to vehicle (B)."""
    p = p or model.load_params()
    link = model.build_links(p, signed, ecc)[link_key]
    return _run_flights(link, [("A", "firmware", int(nbytes))], proto, loss,
                        seed, p)


def mean_wall(fn, seeds, **kw):
    """Mean wall time over seeds; fn is run_handshake or run_firmware."""
    vals = [fn(seed=s, **kw).wall_s for s in seeds]
    return sum(vals) / len(vals)
