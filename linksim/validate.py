"""Validation of the size based timing model against a published link figure.

Author: Huda Mueen.

Target: Table 5 of ePrint 2026/2343 (rows S10F-131 to S10F-150 of
data/evidence.csv), a TLS 1.3 handshake between two Linux network namespaces
over an emulated UAV profile (57.6 kbps, 40 ms delay, Section 4.1 of the
paper), with the measured median time on a clear link and on the UAV link
and the bytes on the wire in each direction.

Model (estimated): t_uav = t_clear + R x 2 x delay + 8 x bytes / rate, where
t_clear is the published clear link time (process and provider setup), R is
the ASSUMPTION tls_round_trips and bytes is read plus written. A second
variant adds the ASSUMPTION per segment TCP and IP header bytes. The error of
each prediction against the published UAV time is reported. Both directions
are assumed to carry the delay; the paper does not say whether netem shaped
one or both directions, which is a stated limit of this check.
"""
import csv
import os
import re

from . import model

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCE = os.path.join(ROOT, "data", "evidence.csv")
SOURCE = "eprint.iacr.org/2026/2343"
TIME_RE = re.compile(r"reported time:\s*([0-9.]+)\s*ms")


def load_table5(path=EVIDENCE):
    """{parameter_set: {clear_ms, uav_ms, rd, wr, ids}} from the evidence table."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if SOURCE not in r["source_url"]:
                continue
            op = r["operation"]
            if not op.startswith("handshake (two node"):
                continue
            d = out.setdefault(r["parameter_set"], {"ids": []})
            d["ids"].append(r["id"])
            m = TIME_RE.search(r["compiler_flags_or_notes"])
            if m and "clear profile" in op:
                d["clear_ms"] = float(m.group(1))
            elif m and "UAV profile" in op:
                d["uav_ms"] = float(m.group(1))
            elif r["size_kind"].endswith("server to client"):
                d["rd"] = int(float(r["key_or_sig_size_bytes"]))
            elif r["size_kind"].endswith("client to server"):
                d["wr"] = int(float(r["key_or_sig_size_bytes"]))
    return {k: v for k, v in out.items()
            if all(x in v for x in ("clear_ms", "uav_ms", "rd", "wr"))}


def tcp_overhead_bytes(nbytes, mss, hdr):
    """Header bytes for one direction: ceil(n / mss) segments times hdr."""
    return model.frames_for_bytes(nbytes, mss) * hdr


def predict_ms(row, p, with_tcp=False):
    """Predicted UAV handshake time in ms for one Table 5 row."""
    link = model.Link("uav", "UAV profile", "stream",
                      p["uav_profile_rate_bps"], int(p["tcp_mss_bytes"]),
                      0, 1.0, 0.0)
    nbytes = row["rd"] + row["wr"]
    if with_tcp:
        nbytes += (tcp_overhead_bytes(row["rd"], p["tcp_mss_bytes"],
                                      p["tcp_ip_header_bytes"])
                   + tcp_overhead_bytes(row["wr"], p["tcp_mss_bytes"],
                                        p["tcp_ip_header_bytes"]))
    rtt = 2.0 * p["uav_profile_delay_s"]
    return row["clear_ms"] + 1000.0 * (p["tls_round_trips"] * rtt
                                       + link.air_s(nbytes))


def run(p=None, path=EVIDENCE, baseline="P-256"):
    """Rows with measured and predicted times, errors, and the difference to
    the baseline group (measured versus predicted)."""
    p = p or model.load_params()
    t5 = load_table5(path)
    out = []
    for name in sorted(t5):
        row = t5[name]
        res = {"group": name, "ids": " ".join(sorted(row["ids"])),
               "rd": row["rd"], "wr": row["wr"],
               "clear_ms": row["clear_ms"], "uav_ms": row["uav_ms"]}
        for tag, tcp in (("plain", False), ("tcp", True)):
            pred = predict_ms(row, p, tcp)
            res["pred_" + tag] = pred
            res["err_" + tag] = pred / row["uav_ms"] - 1.0
        out.append(res)
    if baseline in t5:
        b = [r for r in out if r["group"] == baseline][0]
        for r in out:
            r["meas_diff"] = r["uav_ms"] - b["uav_ms"]
            for tag in ("plain", "tcp"):
                pd = r["pred_" + tag] - b["pred_" + tag]
                r["pred_diff_" + tag] = pd
                r["diff_err_" + tag] = (pd / r["meas_diff"] - 1.0
                                        if r["meas_diff"] else float("nan"))
    return out


# ---------------------------------------------------------------------------
# Third round (2026-10-18): held out calibration, a prose cross check, and
# which parts of the model any published figure can check at all.

TRAIN = ("P-256", "SMAUG-T1")          # fixed by name in docs/PREDICTIONS_V3.md (R7)
TEST = ("ML-KEM-768", "SMAUG-T3", "NTRU+-768")


def held_out(p=None, path=EVIDENCE, train=TRAIN, test=TEST):
    """Fit one fixed overhead term c (ms) on the training groups by least squares,
    c = mean(published - predicted), then predict the held out groups with it.
    Never fits and tests on the same group."""
    p = p or model.load_params()
    t5 = load_table5(path)
    if set(train) & set(test):
        raise ValueError("train and test overlap")
    base = {g: predict_ms(t5[g], p) for g in list(train) + list(test)}
    c = sum(t5[g]["uav_ms"] - base[g] for g in train) / len(train)
    out = []
    for g in list(train) + list(test):
        pred = base[g] + c
        out.append({"group": g, "split": "train" if g in train else "test", "uav_ms": t5[g]["uav_ms"],
                    "pred_uncal_ms": base[g], "fitted_overhead_ms": c, "pred_cal_ms": pred,
                    "err_cal": pred / t5[g]["uav_ms"] - 1.0})
    return out


# Prose statement, not a table, so it is not in data/evidence.csv: ePrint 2021/781 (author supplied PDF),
# pages 15 to 16, says transferring 50 kB over a low power IEEE 802.15.4 link takes 30 to 60 s depending on
# link quality and network load. Used only as a cross check, never to calibrate.
PROSE_802154 = {"bytes": 50000, "low_s": 30.0, "high_s": 60.0,
                "source": "ePrint 2021/781, pages 15 to 16, prose (not a table; not in the evidence table)"}


def crosscheck_802154(p=None, proto="sr"):
    """Model time for the prose object size on the 802.15.4 profile, no loss, and its factor to the prose range."""
    from . import sim
    p = p or model.load_params()
    t = sim.run_firmware("ieee802154", PROSE_802154["bytes"], proto, 0.0, 1, p).wall_s
    return {"bytes": PROSE_802154["bytes"], "proto": proto, "model_s": t, "prose_low_s": PROSE_802154["low_s"],
            "prose_high_s": PROSE_802154["high_s"], "factor_below_low": PROSE_802154["low_s"] / t,
            "source": PROSE_802154["source"]}


PARTS = [
    ("rate (bytes over bit rate)", "validated", "Table 5 of ePrint 2026/2343, rows S10F-131 to S10F-150"),
    ("round trips and fixed overhead", "calibrated on 2 groups, tested on 3 held out groups",
     "Table 5 of ePrint 2026/2343"),
    ("fragmentation and per fragment overhead", "unvalidated",
     "no published measured figure; the 802.15.4 prose figure of ePrint 2021/781 mixes fragmentation with "
     "multi hop forwarding and network load and serves only as a cross check"),
    ("duty cycle", "unvalidated", "no published measured figure in the evidence table or the supplied PDFs"),
    ("loss and retransmission", "unvalidated", "no published measured figure in the evidence table or the supplied PDFs"),
]
