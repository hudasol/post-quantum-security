"""Fragmentation and handshake model for the lowest rate radio profiles.

Author: Huda Mueen.

Profiles come from cited rows of params.csv (LoRaWAN regional parameters as
summarised in data/raw/S3_robotics.md). The fragment header and the LoRaWAN
PHY and MAC overhead are ASSUMPTIONS and are swept, not fixed. US915 DR0 has
a cited payload limit but no cited bit rate, so only fragment counts are
given for it. Size and timing arithmetic only; no cryptography. All results
are estimated from published sizes, not measured.
"""
from . import model

# name: (label, payload param, rate param or None, duty)
PROFILES = {
    "eu868_dr0": ("LoRaWAN EU868 DR0", "lorawan_dr0_payload_bytes",
                  "lorawan_dr0_bitrate_bps", "lorawan_duty_cycle"),
    "eu868_dr5": ("LoRaWAN EU868 DR5", "lorawan_dr5_payload_bytes",
                  "lorawan_dr5_bitrate_bps", "lorawan_duty_cycle"),
    "us915_dr0": ("LoRaWAN US915 DR0", "lorawan_us915_dr0_payload_bytes",
                  None, None),
}
FRAG_HEADERS = (0, 1, 2, 4)      # ASSUMPTION sweep, bytes per fragment
MAC_OVERHEADS = (0, 13)          # ASSUMPTION probe, bytes per frame
VARIANTS = ("hybrid", "hybrid_prov", "classical")


def profile_link(p, name, frag_hdr=0, mac_overhead=0):
    """Link for a profile, or None when the profile has no cited rate.

    The fragment header takes data bytes out of the cited payload; the MAC
    overhead adds wire bytes that do not reduce the payload."""
    label, pay, rate, duty = PROFILES[name]
    cap = int(p[pay]) - int(frag_hdr)
    if cap < 1:
        raise ValueError("fragment header leaves no payload")
    if rate is None:
        return None
    return model.Link(name, label, "packet", p[rate], cap,
                      int(frag_hdr) + int(mac_overhead), p[duty],
                      p["turnaround_lorawan_s"])


def fragments(p, name, nbytes, frag_hdr=0):
    """Fragments needed for nbytes on a profile, rate or not."""
    cap = int(p[PROFILES[name][1]]) - int(frag_hdr)
    if cap < 1:
        raise ValueError("fragment header leaves no payload")
    return model.frames_for_bytes(nbytes, cap)


def handshake_fragments(p, name, variant="hybrid", frag_hdr=0):
    """Total fragments over the three flights of a handshake variant."""
    return sum(fragments(p, name, b, frag_hdr)
               for _, _, b in model.handshake_flights(p, variant))


def one_way_floor_s(p, name, variant="hybrid", frag_hdr=0, mac_overhead=0):
    """Lower bound on handshake wall time with no loss and no
    acknowledgements: each flight is sent back to back under its sender's
    duty cycle, flights follow each other, and one LoRaWAN turnaround
    separates flights. None when the profile has no cited rate."""
    L = profile_link(p, name, frag_hdr, mac_overhead)
    if L is None:
        return None
    flights = model.handshake_flights(p, variant)
    total = 0.0
    for i, (_, _, b) in enumerate(flights):
        total += model.blast_wall_s(L, b)
        if i < len(flights) - 1:
            total += L.turnaround_s
    return total


def table(p=None):
    """Rows for every profile, variant, fragment header and MAC overhead."""
    p = p or model.load_params()
    rows = []
    for name in PROFILES:
        for variant in VARIANTS:
            for hdr in FRAG_HEADERS:
                for mac in MAC_OVERHEADS:
                    if PROFILES[name][2] is None and mac:
                        continue
                    floor = one_way_floor_s(p, name, variant, hdr, mac)
                    rows.append({
                        "profile": name, "label": PROFILES[name][0],
                        "variant": variant, "frag_hdr_bytes": hdr,
                        "mac_overhead_bytes": mac,
                        "fragments": handshake_fragments(p, name, variant, hdr),
                        "floor_wall_s": "" if floor is None else floor,
                    })
    return rows
