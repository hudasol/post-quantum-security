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
