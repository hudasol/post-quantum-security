"""IEEE 802.15.4 frame timing with 6LoWPAN fragmentation (fourth round).

Author: Huda Mueen.

Size and timing arithmetic only; no cryptographic operation. Every constant
comes from linksim/params.csv rows tagged cited (data/raw/S12_link_sources.md)
unless named as an ASSUMPTION. The model is used to diagnose, one cause at a
time, why the size based model is faster than the prose figure of ePrint
2021/781 (pages 15 to 16). It is not tuned to that figure.

Causes, each switched on by a flag (cumulative in validate_v4.DIAG_STEPS):
  phy        SHR and PHR (preamble 4, SFD 1, PHR 1 octets) on every frame
  frag       6LoWPAN FRAG1/FRAGN headers, 8 octet alignment, one IPv6
             datagram per sixlowpan_datagram_bytes (ASSUMPTION)
  mac_ack    a 5 octet ACK PSDU after aTurnaroundTime for every frame
  ifs        LIFS after frames longer than 18 octets, SIFS otherwise
  csma       mean initial random backoff (macMinBE) plus one CCA
  turnaround RX to TX turnaround between CCA and transmission
The mean backoff is used (no contention, idle channel), so the per frame time
is deterministic.
"""
import copy

from . import model

FLAGS = ("phy", "frag", "mac_ack", "ifs", "csma", "turnaround")


def sixlowpan_fragment_payloads(dgram_bytes, avail, frag1=4, fragn=5, unit=8):
    """Payload bytes carried by each link frame for one datagram (RFC 4944
    Section 5.3). avail is the MAC payload room per frame. A datagram that
    fits in one frame is sent without a fragment header. Otherwise every
    fragment except the last carries a multiple of unit octets."""
    dgram_bytes = int(dgram_bytes)
    if dgram_bytes <= 0:
        return []
    if dgram_bytes <= avail:
        return [dgram_bytes]
    first = ((avail - frag1) // unit) * unit
    nxt = ((avail - fragn) // unit) * unit
    if first <= 0 or nxt <= 0:
        raise ValueError("frame too small for a 6LoWPAN fragment")
    out = [first]
    left = dgram_bytes - first
    while left > nxt:
        out.append(nxt)
        left -= nxt
    out.append(left)
    return out


def sixlowpan_headers(payloads):
    """Fragment header bytes per frame for the list from
    sixlowpan_fragment_payloads: 0 for an unfragmented datagram, else 4 for
    the first and 5 for each later fragment."""
    if len(payloads) <= 1:
        return [0] * len(payloads)
    return [4] + [5] * (len(payloads) - 1)


class Mac802154Link(model.Link):
    """802.15.4 link whose air_s includes the per frame MAC and PHY costs
    selected by flags. kind 'packet'; duty 1.0."""

    def __init__(self, p, flags=(), turnaround_s=None):
        flags = tuple(flags)
        for f in flags:
            if f not in FLAGS:
                raise ValueError(f)
        self.flags = flags
        self.p = p
        cap = int(p["ieee802154_data_bytes"])
        ovh = int(p["ieee802154_phy_max_bytes"] - p["ieee802154_data_bytes"])
        self.shr = int(p["ieee802154_shr_phr_bytes"]) if "phy" in flags else 0
        model.Link.__init__(self, "ieee802154_v4", "IEEE 802.15.4 (v4 frame model)",
                            "packet", p["ieee802154_rate_bps"], cap, ovh + self.shr,
                            1.0, p["turnaround_s"] if turnaround_s is None else turnaround_s)
        sym = p["ieee802154_symbol_s"]
        self.sym = sym
        self.extra_fixed = 0.0
        if "mac_ack" in flags:
            ack_wire = p["ieee802154_ack_psdu_bytes"] + (self.shr if self.shr else 0)
            self.extra_fixed += (p["ieee802154_turnaround_symbols"] * sym
                                 + 8.0 * ack_wire / self.rate_bps)
        if "csma" in flags:
            mean_units = (2 ** int(p["ieee802154_min_be"]) - 1) / 2.0
            self.extra_fixed += (mean_units * p["ieee802154_unit_backoff_symbols"] * sym
                                 + p["ieee802154_cca_symbols"] * sym)
        if "turnaround" in flags:
            self.extra_fixed += p["ieee802154_turnaround_symbols"] * sym

    def frame_extra_s(self, wire_bytes):
        """Per frame time besides the frame's own air time."""
        e = self.extra_fixed
        if "ifs" in self.flags:
            psdu = wire_bytes - self.shr
            syms = (self.p["ieee802154_lifs_symbols"]
                    if psdu > self.p["ieee802154_sifs_max_frame_bytes"]
                    else self.p["ieee802154_sifs_symbols"])
            e += syms * self.sym
        return e

    def air_s(self, wire_bytes):
        return 8.0 * wire_bytes / self.rate_bps + self.frame_extra_s(wire_bytes)

    def fragment_wire_sizes(self, n_bytes):
        n_bytes = int(n_bytes)
        if n_bytes <= 0:
            return []
        if "frag" not in self.flags:
            nf = model.frames_for_bytes(n_bytes, self.cap)
            last = n_bytes - (nf - 1) * self.cap
            return [self.wire_bytes(self.cap)] * (nf - 1) + [self.wire_bytes(last)]
        dg = int(self.p["sixlowpan_datagram_bytes"])
        out = []
        left = n_bytes
        while left > 0:
            d = min(dg, left)
            pl = sixlowpan_fragment_payloads(
                d, self.cap, int(self.p["sixlowpan_frag1_hdr_bytes"]),
                int(self.p["sixlowpan_fragn_hdr_bytes"]),
                int(self.p["sixlowpan_offset_unit_bytes"]))
            for b, h in zip(pl, sixlowpan_headers(pl)):
                out.append(self.wire_bytes(b + h))
            left -= d
        return out


def build(p=None, flags=()):
    p = p or model.load_params()
    return Mac802154Link(p, flags)


def multihop_wall_s(wall_one_hop_s, hops):
    """Store and forward over hops on one shared channel without spatial
    reuse: each hop repeats the whole transfer (ASSUMPTION; an upper style
    bound used only as a sweep)."""
    if hops < 1:
        raise ValueError("hops must be at least 1")
    return wall_one_hop_s * hops


def copy_link(link):
    return copy.copy(link)
