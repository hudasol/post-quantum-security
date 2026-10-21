"""Scenario cells, seeds and settings of the network simulator check.

Author: Huda Mueen.

Every cell has its own block of ns-3 run numbers (independent substreams of
the global seed 20261021), so no two cells share a random stream. The
settings table records the source of every setting: the paper (ePrint
2021/781), the ns-3 default at the pinned version, linksim/params.csv, or an
ASSUMPTION of this study.
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20261021
OBJECT_BYTES = 50000
# Object bytes per segment in the frame mode: the largest segment whose UDP
# datagram still fits one IEEE 802.15.4 frame after 6LoWPAN IPHC compression
# in ns-3 (checked by the frames per segment column of lrwpan_runs.csv).
SEG_FRAME = 62
# Datagram mode: one 1280 B IPv6 datagram per segment (linksim/params.csv
# sixlowpan_datagram_bytes, an ASSUMPTION) less 40 B IPv6 and 8 B UDP headers
# and the 10 B header of the selective repeat segment.
SEG_DGRAM = 1280 - 40 - 8 - 10
WINDOW = 16       # linksim/params.csv sr_window_frames
RTO_FACTOR = 2.0  # linksim/params.csv rto_factor
MAX_RETRIES = 20  # linksim/params.csv max_retries
PROSE_LOW_S = 30.0
PROSE_HIGH_S = 60.0
# Agreement with the model: ns-3 time within this fraction of the linksim
# time at the same setting. Fixed before the sweep was run.
MODEL_TOL = 0.20

BASE = {"hops": 1, "bgNodes": 0, "bgInterval": 0.1, "bgBytes": 50, "spacing": 20.0,
        "minBe": 3, "maxBe": 5, "maxBackoffs": 4, "retries": 3,
        "objectBytes": OBJECT_BYTES, "segBytes": SEG_FRAME, "window": WINDOW,
        "rtoFactor": RTO_FACTOR, "maxRetries": MAX_RETRIES}

# (setting, value, source)
SETTINGS = [
    ("object size", "50000 B", "paper: ePrint 2021/781 pp. 15 to 16 (\"50kB\"); 1 kB = 1000 B is linksim/params.csv kb_bytes (ASSUMPTION)"),
    ("radio", "IEEE 802.15.4, 2.4 GHz O-QPSK, 250 kbps", "paper: \"low-power IEEE802.15.4 radio link\" (pp. 15 to 16), nRF52840 board (Section 5.1); 2.4 GHz O-QPSK is the ns-3 lr-wpan default"),
    ("link quality", "not stated numerically", "paper: \"depending on link quality and network load\"; not given"),
    ("network load", "not stated numerically", "paper: as above; swept here as neighbours with background traffic"),
    ("hop count", "1 (swept 1 to 6)", "paper gives none; ASSUMPTION"),
    ("6LoWPAN", "IPHC header compression, route over static routing", "ns-3 default SixLowPanNetDevice; paper does not state the stack"),
    ("MAC acknowledgements", "on", "ns-3 default (LrWpanNetDevice UseAcks true)"),
    ("macMinBE", "3", "ns-3 default; equals linksim/params.csv ieee802154_min_be"),
    ("macMaxBE", "5", "ns-3 default; equals linksim/params.csv ieee802154_max_be"),
    ("macMaxCSMABackoffs", "4", "ns-3 default; equals linksim/params.csv ieee802154_max_csma_backoffs"),
    ("macMaxFrameRetries", "3", "ns-3 default; data/raw/S12_link_sources.md B2.2 gives 3"),
    ("ranges swept", "macMinBE 0 to macMaxBE, macMaxBE 3 to 8, macMaxCSMABackoffs 0 to 5, macMaxFrameRetries 0 to 7", "netsim/SOURCES.md N1 (Microchip 15.4 MAC PIB list) and N2 (ns-3 source comments citing IEEE 802.15.4-2006 Table 86)"),
    ("transmit power, sensitivity", "0 dBm, -106.58 dBm", "ns-3 defaults"),
    ("propagation", "log distance loss, constant speed delay", "ns-3 lr-wpan example setup (example-ping-lr-wpan.cc)"),
    ("node spacing", "20 m (10 m as a sensitivity check)", "ASSUMPTION (the ns-3 example spacing); the paper gives no distance"),
    ("transfer protocol", "application level selective repeat over UDP, window 16 segments, timeout 2 x smoothed window round trip, 20 polls", "linksim/sim.py selective_repeat; window, timeout factor and poll limit from linksim/params.csv"),
    ("timer details", "initial timeout 1 s; timeout doubled after each expiry until an acknowledgement without a poll gives a new round trip sample; one small datagram each way before the transfer", "ASSUMPTION of this study (needed because ns-3 has no known air time to derive the timeout from, unlike linksim)"),
    ("segment", "62 B of object per UDP datagram (one frame), or 1222 B (one 1280 B IPv6 datagram, fragmented by 6LoWPAN)", "frame mode: chosen to fit one frame; datagram mode: linksim/params.csv sixlowpan_datagram_bytes (ASSUMPTION)"),
    ("paper's own transfer", "CoAP fetch from a repository (Section 3.1)", "paper; not simulated, the linksim protocol is used instead"),
    ("background traffic", "50 B UDP every 0.1 s per neighbour, each to its own partner 5 m away, 10 m from the line", "ASSUMPTION"),
]

# Frame overhead the lorawan module adds: frame header 8 B plus MAC header 1 B,
# no message integrity code (netsim/SOURCES.md N3.3).
NS3_LORAWAN_OVERHEAD_BYTES = 9

LORA_TOA_SIZES = (13, 20, 24, 30, 40, 51, 64, 100, 150, 200, 235)


def _cell(group, cell, cause, value, runs, **over):
    a = dict(BASE)
    a.update(over)
    return {"group": group, "cell": cell, "cause": cause, "value": value, "args": a, "runs": runs}


def lrwpan_cells():
    """All ns-3 cells. Run numbers: block k uses k*100+1 to k*100+n."""
    out = []
    k = [0]

    def add(group, cell, cause, value, n, **over):
        k[0] += 1
        out.append(_cell(group, cell, cause, value, [k[0] * 100 + i for i in range(1, n + 1)], **over))

    add("S1", "base_frame", "baseline", "frame mode", 10)
    add("S1", "base_dgram", "baseline", "datagram mode", 10, segBytes=SEG_DGRAM)
    for h in (2, 3, 4, 5, 6):
        add("S2 one", "hops_%d" % h, "hops", h, 5, hops=h)
    for n in (1, 2, 4, 8, 16):
        add("S2 one", "bg_%d" % n, "neighbours", n, 5, bgNodes=n)
    for be in (0, 1, 2, 4, 5):
        add("S2 one", "minbe_%d" % be, "macMinBE", be, 3, minBe=be)
    for be in (6, 7, 8):
        add("S2 one", "minbe_%d" % be, "macMinBE", be, 3, minBe=be, maxBe=8)
    for be in (3, 4, 6, 7, 8):
        add("S2 one", "maxbe_%d" % be, "macMaxBE", be, 3, maxBe=be, minBe=min(3, be))
    for b in (0, 1, 2, 3, 5):
        add("S2 one", "backoffs_%d" % b, "macMaxCSMABackoffs", b, 3, maxBackoffs=b)
    for r in (0, 1, 2, 4, 5, 6, 7):
        add("S2 one", "retries_%d" % r, "macMaxFrameRetries", r, 3, retries=r)
    for h in (2, 3, 4, 6):
        for n in (2, 4, 8):
            add("S2 combined", "hops_%d_bg_%d" % (h, n), "hops and neighbours", "%d hops, %d neighbours" % (h, n),
                3, hops=h, bgNodes=n)
    for h in (2, 3):
        for be in (5, 8):
            add("S2 combined", "hops_%d_minbe_%d" % (h, be), "hops and macMinBE", "%d hops, macMinBE %d" % (h, be),
                3, hops=h, minBe=be, maxBe=max(5, be))
    for h in (2, 3, 4):
        add("S2 combined", "hops_%d_spacing_10" % h, "hops, spacing 10 m", "%d hops, 10 m spacing" % h, 3,
            hops=h, spacing=10.0)
    for h in (2, 3, 4):
        add("S2 combined", "dgram_hops_%d" % h, "hops, datagram mode", "%d hops, datagram mode" % h, 3,
            hops=h, segBytes=SEG_DGRAM)
    # Follow up, added after the sweep: ten more runs, in new run blocks, of
    # each one at a time cell that landed in the published range.
    add("S3 follow up", "follow_hops_3", "hops", 3, 10, hops=3)
    add("S3 follow up", "follow_bg_16", "neighbours", 16, 10, bgNodes=16)
    add("S3 follow up", "follow_minbe_8", "macMinBE", 8, 10, minBe=8, maxBe=8)
    return out


def lora_flights(path=None):
    """Handshake flights (variant hybrid, scenario ttfam, without the command
    sent after the handshake) of linksim's protocol profiles:
    [(protocol, [(side, bytes), ...])].

    Read from netsim/results/ns3_handshake_flights.csv, a frozen copy of
    linksim/results/protocols_flights.csv as it was when the ns-3 runs were
    made (round 4 handshake, before design change F1 of
    docs/FORMAL_VERIFICATION.md added the vehicle signature), so that the
    ns-3 results and the linksim side of the comparison use the same flights."""
    path = path or os.path.join(ROOT, "netsim", "results", "ns3_handshake_flights.csv")
    by = {}
    order = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["scenario"] != "ttfam" or r["variant"] != "hybrid" or r["message"] == "authenticated command":
                continue
            if r["protocol"] not in by:
                by[r["protocol"]] = []
                order.append(r["protocol"])
            by[r["protocol"]].append((r["sender"], int(r["bytes"])))
    return [(p, by[p]) for p in order]
