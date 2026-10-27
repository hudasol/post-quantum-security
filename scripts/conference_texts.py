#!/usr/bin/env python3
"""Text of the conference paper (IEEE conference format, LaTeX), generated with numbers read from result files.

Called by scripts/build_paper.py, which passes its claim() function, so every number below is registered in
data/claims_register.csv and checked by scripts/check_numbers.py. Two documents are written: the paper with the
author block (docs/conference/paper.tex) and an anonymised copy for double blind review
(docs/conference/paper_anon.tex). scripts/build_conference_pdf.sh compiles both with pdflatex and bibtex.
References come from data/conference/references.csv (each row traced to a retrieved source).
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = "docs/conference/paper.tex"
DOC_ANON = "docs/conference/paper_anon.tex"
SES = "rtlsim/results/proto_sessions.csv"
PRIM = "rtlsim/results/proto_primitives.csv"
SIZES = "rtlsim/results/proto_sizes.csv"
TIME = "rtlsim/results/proto_time_estimated.csv"
PV = "formal/results/proverif_results.csv"
FS = "planner/results/flightstack_mc_summary.csv"
FM = "data/flightstack_memory.csv"
REPO = "https://github.com/hudasol/post-quantum-security"
DER = "data/conference/derived.csv"


def write_derived():
    """Ratios of the RTL simulated medians used by the paper, written to data/conference/derived.csv."""
    import pandas as pd
    s = pd.read_csv(ROOT / SES)

    def v(core, d, side, col="cycles_median", unit="session start"):
        return float(s[(s.core == core) & (s.design == d) & (s.side == side) & (s.unit == unit)][col].iloc[0])
    rows = []
    for core in ("ibex", "cv32e40p"):
        tag = v(core, "mavlink_tag", "vehicle", unit="per message, tag alone, COMMAND_LONG")
        pqc = float(s[(s.core == core) & (s.design == "per_command_mldsa44") & (s.side == "vehicle")].cycles_median.iloc[0])
        for k, val, basis in (
                ("hyb_over_cls_vehicle", v(core, "hybrid_f1", "vehicle") / v(core, "classical", "vehicle"), "hybrid_f1 over classical, vehicle, session start"),
                ("hyb_over_pq_vehicle", v(core, "hybrid_f1", "vehicle") / v(core, "pq_only", "vehicle"), "hybrid_f1 over pq_only, vehicle, session start"),
                ("hyb_over_cls_ground", v(core, "hybrid_f1", "ground") / v(core, "classical", "ground"), "hybrid_f1 over classical, ground, session start"),
                ("pqc_over_tag_vehicle", pqc / tag, "ML-DSA-44 verify per command over the tag check of the same COMMAND_LONG frame, vehicle"),
                ("bytes_hyb_over_cls", v(core, "hybrid_f1", "vehicle", "bytes_total") / v(core, "classical", "vehicle", "bytes_total"), "session start bytes on air, hybrid_f1 over classical")):
            rows.append({"label": "RTL simulated", "core": core, "ratio": k, "value": round(val, 6), "basis": basis, "source": SES})
    rows.append({"label": "RTL simulated", "core": "ibex over cv32e40p", "ratio": "hyb_vehicle",
                 "value": round(v("ibex", "hybrid_f1", "vehicle") / v("cv32e40p", "hybrid_f1", "vehicle"), 6),
                 "basis": "hybrid_f1 vehicle session start, Ibex over CV32E40P", "source": SES})
    with open(ROOT / DER, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def tex_escape(s):
    return (s.replace("\\", "\\textbackslash{}").replace("&", "\\&").replace("%", "\\%").replace("_", "\\_")
            .replace("#", "\\#").replace("$", "\\$"))


def bib():
    """BibTeX entries from data/conference/references.csv."""
    out = []
    for r in csv.DictReader(open(ROOT / "data/conference/references.csv", encoding="utf-8")):
        out.append("@misc{%s,\n  author = {%s},\n  title = {{%s}},\n  howpublished = {%s, \\url{%s}},\n  year = {%s}\n}\n"
                   % (r["key"], r["author"], r["title"].replace("&", "\\&"), r["venue"].replace("&", "\\&"), r["url"], r["year"]))
    return "\n".join(out)


def numbers(c, doc):
    """Every number of the paper, read through claim() for the given document."""
    def ses(cid, core, design, side, col="cycles_median", scale=1e-6, fmt="{:.1f}", label="RTL simulated"):
        q = f'core == "{core}" and design == "{design}" and side == "{side}" and unit == "session start"'
        return c(cid, SES, col, q, fmt=fmt, scale=scale, label=label, doc=doc)

    n = {}
    for core in ("ibex", "cv32e40p"):
        for d in ("classical", "pq_only", "hybrid_f1"):
            for side in ("vehicle", "ground"):
                n[f"{core}_{d}_{side}"] = ses(f"cf_{core}_{d}_{side}", core, d, side)
        n[f"{core}_hyb_stack"] = ses(f"cf_{core}_hyb_stack", core, "hybrid_f1", "vehicle", "peak_stack_bytes", 1e-3, "{:.1f}")
        n[f"{core}_cls_stack"] = ses(f"cf_{core}_cls_stack", core, "classical", "vehicle", "peak_stack_bytes", 1e-3, "{:.1f}")
        n[f"{core}_pqc_v"] = c(f"cf_{core}_pqc_v", SES, "cycles_median",
                               f'core == "{core}" and design == "per_command_mldsa44" and side == "vehicle"', fmt="{:.1f}", scale=1e-6,
                               label="RTL simulated", doc=doc)
        n[f"{core}_tag"] = c(f"cf_{core}_tag", SES, "cycles_median",
                             f'core == "{core}" and design == "mavlink_tag" and unit == "per message, tag alone" and side == "vehicle"',
                             fmt="{:,.0f}", label="RTL simulated", doc=doc)
        n[f"{core}_x25519"] = c(f"cf_{core}_x25519", PRIM, "cycles_median", f'core == "{core}" and operation == "x25519_shared"',
                                fmt="{:.2f}", scale=1e-6, label="RTL simulated", doc=doc)
        n[f"{core}_encaps"] = c(f"cf_{core}_encaps", PRIM, "cycles_median", f'core == "{core}" and operation == "mlkem768_encaps"',
                                fmt="{:.2f}", scale=1e-6, label="RTL simulated", doc=doc)
    for d in ("classical", "pq_only", "hybrid_f1"):
        n[f"bytes_{d}"] = c(f"cf_bytes_{d}", SES, "bytes_total", f'core == "cv32e40p" and design == "{d}" and side == "vehicle"',
                            fmt="{:,.0f}", label="RTL simulated", doc=doc)
    n["t168_hyb"] = c("cf_t168_hyb", TIME, "time_ms", 'core == "cv32e40p" and design == "hybrid_f1" and side == "vehicle" and clock_mhz == 168',
                      fmt="{:.0f}", label="estimated", doc=doc)
    n["t168_cls"] = c("cf_t168_cls", TIME, "time_ms", 'core == "cv32e40p" and design == "classical" and side == "vehicle" and clock_mhz == 168',
                      fmt="{:.0f}", label="estimated", doc=doc)
    n["t64_hyb_ibex"] = c("cf_t64_hyb_ibex", TIME, "time_ms", 'core == "ibex" and design == "hybrid_f1" and side == "vehicle" and clock_mhz == 64',
                          fmt="{:.0f}", label="estimated", doc=doc)
    # ratios, written by write_derived() from the same rows and read back through claim()
    for core in ("ibex", "cv32e40p"):
        for k in ("hyb_over_cls_vehicle", "hyb_over_pq_vehicle", "hyb_over_cls_ground", "pqc_over_tag_vehicle", "bytes_hyb_over_cls"):
            n[f"{core}_{k}"] = c(f"cf_{core}_{k}", DER, "value", f'core == "{core}" and ratio == "{k}"', fmt="{:.2f}" if "tag" not in k and "bytes" not in k else "{:.0f}",
                                 label="RTL simulated", doc=doc)
    n["core_ratio_hyb"] = c("cf_core_ratio_hyb", DER, "value", 'core == "ibex over cv32e40p" and ratio == "hyb_vehicle"', fmt="{:.2f}",
                            label="RTL simulated", doc=doc)
    # formal
    n["pv_q"] = c("cf_pv_q", PV, "result", aggregate="count", label="modelled", doc=doc)
    n["pv_m"] = c("cf_pv_m", PV, "model", aggregate="nunique", label="modelled", doc=doc)
    n["pv_p"] = c("cf_pv_p", PV, "result", 'result == "proved"', "count", label="modelled", doc=doc)
    n["pv_cx"] = c("cf_pv_cx", PV, "result", 'result == "counterexample"', "count", label="modelled", doc=doc)
    n["pv_cnp"] = c("cf_pv_cnp", PV, "result", 'result == "cannot be proved"', "count", label="modelled", doc=doc)
    # flight stack memory
    n["fs_builds"] = c("cf_fs_builds", FM, "build_status", 'build_status == "built"', "count", label="host measured", doc=doc)
    n["fs_boards"] = c("cf_fs_boards", FS, "measured_boards", 'thresholds == "uncertain"', fmt="{:.0f}", label="estimated", doc=doc)
    n["px4_min"] = c("cf_px4_min", FM, "flash_free_bytes", 'stack == "px4"', "min", "{:,.0f}", label="host measured", doc=doc)
    n["hr_a"] = c("cf_hr_a", FS, "assumed_median", 'thresholds == "uncertain"', fmt="{:.2f}", label="estimated", doc=doc)
    n["hr_m"] = c("cf_hr_m", FS, "measured_median", 'thresholds == "uncertain"', fmt="{:.2f}", label="estimated", doc=doc)
    n["hr_c"] = c("cf_hr_c", FS, "crash_log_used_median", 'thresholds == "uncertain"', fmt="{:.2f}", label="estimated", doc=doc)
    return n
