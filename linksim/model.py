"""Frame, fragment and timing arithmetic for the link simulator.

Author: Huda Mueen.

This module performs size and timing arithmetic only. It implements no
cryptographic primitive. All results are estimated from published sizes,
not measured.
"""
import csv
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_CSV = os.path.join(HERE, "params.csv")
FOOTER = "estimated from published sizes, not measured"

LINK_ORDER = ["sik", "lorawan", "ieee802154", "ble", "generic1m", "generic10k"]


def load_param_rows(path=PARAMS_CSV):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def load_params(path=PARAMS_CSV, overrides=None):
    """Return {name: float}. Overrides replace values by name."""
    p = {r["name"]: float(r["value"]) for r in load_param_rows(path)}
    if overrides:
        for k, v in overrides.items():
            if k not in p:
                raise KeyError(k)
            p[k] = float(v)
    return p


class Link:
    """A link model.

    kind: 'stream' (bytes in a serial radio stream, MAVLink framed) or
          'packet' (fixed maximum payload per radio frame).
    cap: data bytes carried per bulk fragment.
    overhead: wire bytes added to each bulk fragment.
    duty: duty cycle fraction (1.0 means unrestricted).
    """

    def __init__(self, key, label, kind, rate_bps, cap, overhead, duty,
                 turnaround_s):
        self.key = key
        self.label = label
        self.kind = kind
        self.rate_bps = float(rate_bps)
        self.cap = int(cap)
        self.overhead = int(overhead)
        self.duty = float(duty)
        self.turnaround_s = float(turnaround_s)

    def wire_bytes(self, data_bytes):
        return int(data_bytes) + self.overhead

    def air_s(self, wire_bytes):
        return 8.0 * wire_bytes / self.rate_bps

    def off_s(self, air_s):
        """Mandatory silence after a transmission of air_s seconds."""
        if self.duty >= 1.0:
            return 0.0
        return air_s * (1.0 / self.duty - 1.0)


def build_links(p, signed=False, ecc=False):
    """Build the six links. signed adds the 13 B MAVLink signing field to
    every MAVLink framed fragment (stream links only). ecc halves the SiK rate.
    """
    sig = p["mav_sig_field_bytes"] if signed else 0
    mav_ovh = (p["mav_header_bytes"] + p["mav_checksum_bytes"]
               + p["mav_ftp_header_bytes"] + sig)
    ftp = int(p["mav_ftp_data_bytes"])
    fh = int(p["frag_hdr_bytes"])
    sik_rate = (p["sik_air_rate_bps"] * p["sik_usable_fraction"]
                * (p["sik_ecc_factor"] if ecc else 1.0))
    td = p["turnaround_s"]
    links = {
        "sik": Link("sik", "SiK 64 kbps", "stream", sik_rate, ftp, mav_ovh,
                    1.0, td),
        "lorawan": Link("lorawan", "LoRaWAN EU868 DR0", "packet",
                        p["lorawan_dr0_bitrate_bps"],
                        p["lorawan_dr0_payload_bytes"] - fh,
                        fh + p["lorawan_phy_mac_overhead_bytes"],
                        p["lorawan_duty_cycle"], p["turnaround_lorawan_s"]),
        "ieee802154": Link("ieee802154", "IEEE 802.15.4", "packet",
                           p["ieee802154_rate_bps"],
                           p["ieee802154_data_bytes"] - fh,
                           fh + p["ieee802154_phy_max_bytes"]
                           - p["ieee802154_data_bytes"], 1.0, td),
        "ble": Link("ble", "BLE", "packet", p["ble_rate_bps"],
                    p["ble_upper_payload_bytes"] - fh,
                    fh + p["ble_ll_mtu_bytes"] - p["ble_upper_payload_bytes"],
                    1.0, td),
        "generic1m": Link("generic1m", "Generic 1 Mbps", "stream",
                          p["generic_fast_rate_bps"], ftp, mav_ovh, 1.0, td),
        "generic10k": Link("generic10k", "Generic 10 kbps", "stream",
                           p["generic_slow_rate_bps"], ftp, mav_ovh, 1.0, td),
    }
    return links


def frames_for_bytes(n_bytes, cap):
    """ceil(n / cap); zero bytes need zero frames."""
    if n_bytes <= 0:
        return 0
    return -(-int(n_bytes) // int(cap))


def fragment_wire_sizes(link, n_bytes):
    """Wire size of each fragment of an n_bytes object."""
    nf = frames_for_bytes(n_bytes, link.cap)
    if nf == 0:
        return []
    last = n_bytes - (nf - 1) * link.cap
    return [link.wire_bytes(link.cap)] * (nf - 1) + [link.wire_bytes(last)]


def transfer_air_s(link, n_bytes):
    """Air time of one pass over all fragments, no loss, no acknowledgements."""
    return sum(link.air_s(w) for w in fragment_wire_sizes(link, n_bytes))


def blast_wall_s(link, n_bytes):
    """Wall time to send all fragments back to back, honouring the duty cycle.

    After each transmission the sender is silent for air * (1/duty - 1). The
    silence after the final fragment does not delay delivery.
    Example (hand check in tests): LoRaWAN, 1 fragment: wall = air.
    """
    sizes = fragment_wire_sizes(link, n_bytes)
    total = 0.0
    for i, w in enumerate(sizes):
        a = link.air_s(w)
        total += a
        if i < len(sizes) - 1:
            total += link.off_s(a)
    return total


def handshake_flights(p, variant="hybrid"):
    """List of (sender, label, bytes). A is the ground side (initiator),
    B is the vehicle (responder).

    hybrid:       F1 X25519 share + ML-KEM-768 encapsulation key
                  F2 X25519 share + ML-KEM-768 ciphertext + ML-DSA-44 sig + pk
                  F3 key confirmation
    hybrid_prov:  as hybrid but the ML-DSA-44 public key is provisioned, so
                  it is not sent.
    classical:    X25519 plus Ed25519 baseline for comparison.
    """
    x = p["x25519_share_bytes"]
    c = p["confirm_bytes"]
    if variant in ("hybrid", "hybrid_prov"):
        f1 = x + p["mlkem768_ek_bytes"]
        f2 = x + p["mlkem768_ct_bytes"] + p["mldsa44_sig_bytes"]
        if variant == "hybrid":
            f2 += p["mldsa44_pk_bytes"]
    elif variant == "classical":
        f1 = x
        f2 = x + p["ed25519_sig_bytes"] + p["ed25519_pk_bytes"]
    else:
        raise ValueError(variant)
    return [("A", "F1 initiator key share", int(f1)),
            ("B", "F2 responder share and signature", int(f2)),
            ("A", "F3 key confirmation", int(c))]


def message_air_s(link, p, tag_bytes):
    """Air time of one MAVLink 2 message with a tag of tag_bytes appended.

    Message wire bytes = header + checksum + payload + tag. Stream links send
    it as a continuous byte stream. Packet links split it into fragments.
    """
    m = (p["mav_header_bytes"] + p["mav_checksum_bytes"]
         + p["msg_payload_bytes"] + tag_bytes)
    if link.kind == "stream":
        return 8.0 * m / link.rate_bps
    return transfer_air_s(link, m)


def tag_added_latency_s(link, p, tag_bytes):
    """Added air time of the tag versus an unsigned message."""
    return message_air_s(link, p, tag_bytes) - message_air_s(link, p, 0)


def tag_added_occupancy_s(link, p, tag_bytes):
    """Added channel occupancy including mandatory duty cycle silence."""
    d = tag_added_latency_s(link, p, tag_bytes)
    return d / link.duty if link.duty < 1.0 else d
