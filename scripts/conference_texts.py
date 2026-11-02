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
RAT = "rtlsim/results/proto_ratios.csv"
DEC = "rtlsim/results/proto_decomposition.csv"
PV = "formal/results/proverif_results.csv"
SHARED = "data/shared_inputs.csv"
MA = "mission/assumptions.csv"
SST = "sitl/settings.csv"
RA = "mission/replay_assumptions.csv"
REPO = "https://github.com/hudasol/post-quantum-security"
DER = "data/conference/derived.csv"
SESSION_DESIGNS = ("classical", "pq_only", "hybrid_f1", "kem_auth")
DESIGN_NAMES = {"classical": "Classical", "pq_only": "PQ only", "hybrid_f1": "Hybrid", "kem_auth": "KEM authenticated (K)"}


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
    for d in SESSION_DESIGNS:
        txt = s[(s.core == "cv32e40p") & (s.design == d) & (s.side == "vehicle") & (s.unit == "session start")].bytes_per_flight.iloc[0]
        for part in txt.split(";"):
            fl, _, b = part.strip().split()
            rows.append({"label": "RTL simulated", "core": "cv32e40p", "ratio": f"{d}_{fl.lower()}_bytes", "value": float(b),
                         "basis": f"bytes of flight {fl} as built, {d}", "source": SES})
    pr = pd.read_csv(ROOT / PRIM)
    x = float(pr[(pr.core == "cv32e40p") & (pr.operation.isin(["x25519_keygen", "x25519_shared"]))].cycles_median.sum())
    rows.append({"label": "RTL simulated", "core": "cv32e40p", "ratio": "x25519_pair_cycles", "value": x,
                 "basis": "X25519 key generation plus shared secret, the fixed difference between the hybrid and the post quantum only vehicle side", "source": PRIM})
    rows.append({"label": "RTL simulated", "core": "cv32e40p", "ratio": "hyb_minus_pq_vehicle_cycles",
                 "value": v("cv32e40p", "hybrid_f1", "vehicle") - v("cv32e40p", "pq_only", "vehicle"),
                 "basis": "measured median hybrid_f1 minus pq_only, vehicle, session start", "source": SES})
    sh = pd.read_csv(ROOT / SHARED)
    rate = float(sh[sh.parameter == "sik_air_rate_bps"].value.iloc[0])
    rows.append({"label": "estimated", "core": "link", "ratio": "sig_field_airtime_ms", "value": round(13 * 8 / rate * 1000, 6),
                 "basis": "airtime of the 13 B MAVLink 2 signing field at the SiK air rate, one direction", "source": SHARED})
    sm = pd.read_csv(ROOT / "sitl/results_r6/summary.csv")
    def ow(k):
        return float(sm[(sm.profile == "sik") & (sm.config == k) & (sm.metric == "latency_ow_median_ms")].value.iloc[0])
    rows.append({"label": "emulated", "core": "link", "ratio": "ow_rise_signing_ms", "value": round(ow("signing") - ow("none"), 6),
                 "basis": "median one way latency, signing as shipped minus no authentication", "source": "sitl/results_r6/summary.csv"})
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


ORG_KEYS = {"fips203", "fips204", "mavsign", "ibex", "cv32e40p", "mlkemnative", "mldsanative", "monocypher", "ardupilot"}


def bib():
    """BibTeX entries from data/conference/references.csv: article (journal), inproceedings (conference) or misc.
    The venue field holds the journal or proceedings first and, after a semicolon, further identifiers (ePrint,
    DOI), which go to the note field."""
    def esc(x):
        return x.replace("&", "\\&").replace("_", "\\_")
    out = []
    for r in csv.DictReader(open(ROOT / "data/conference/references.csv", encoding="utf-8")):
        if r["key"] in ORG_KEYS:
            r["author"] = "{" + r["author"] + "}"  # corporate author, kept whole by BibTeX
        head, _, rest = r["venue"].partition(";")
        title = r["title"].replace("&", "\\&")
        # one locator per paper, to save space: the DOI when the record has one, else the ePrint number, else the URL
        ids = [x.strip() for x in rest.split(";") if x.strip()]
        loc = next((x for x in ids if x.startswith("DOI")), None) or next((x for x in ids if "ePrint" in x), None)
        note = esc(loc) if loc else "\\url{%s}" % r["url"]
        if r["type"] == "article":
            fields = [("journal", esc(head.strip())), ("note", note)]
        elif r["type"] == "inproceedings":
            fields = [("booktitle", "Proc.\\ " + esc(head.strip())), ("note", note)]
        else:
            fields = [("howpublished", "%s, \\url{%s}" % (esc(r["venue"]), r["url"]))]
        body = ",\n".join(("  %s = {{%s}}" if kv[0] == "note" else "  %s = {%s}") % kv for kv in [("author", r["author"]), ("title", "{" + title + "}")] + fields + [("year", r["year"])])
        out.append("@%s{%s,\n%s\n}\n" % (r["type"] if r["type"] in ("article", "inproceedings") else "misc", r["key"], body))
    return "\n".join(out)


def numbers(c, doc):
    """Every RTL, formal and set up number of the paper, read through claim() for the given document."""
    def ses(cid, core, design, side, col="cycles_median", scale=1e-6, fmt="{:.1f}", label="RTL simulated"):
        q = f'core == "{core}" and design == "{design}" and side == "{side}" and unit == "session start"'
        return c(cid, SES, col, q, fmt=fmt, scale=scale, label=label, doc=doc)

    def rat(cid, core, side, num, den, col="ratio"):
        q = f'core == "{core}" and side == "{side}" and numerator == "{num}" and denominator == "{den}" and basis == "session medians"'
        return c(cid, RAT, col, q, fmt="{:.2f}", label="RTL simulated", doc=doc)

    n = {}
    n["runs"] = c("cf_runs", SES, "n_runs", 'unit == "session start"', "min", "{:.0f}", label="RTL simulated", doc=doc)
    n["runs_tag"] = c("cf_runs_tag", SES, "n_runs", 'design == "mavlink_tag"', "max", "{:.0f}", label="RTL simulated", doc=doc)
    for core in ("ibex", "cv32e40p"):
        for d in SESSION_DESIGNS:
            for side in ("vehicle", "ground"):
                n[f"{core}_{d}_{side}"] = ses(f"cf_{core}_{d}_{side}", core, d, side)
        for side in ("vehicle", "ground"):
            n[f"{core}_pqc_{side}"] = c(f"cf_{core}_pqc_{side}", SES, "cycles_median",
                                        f'core == "{core}" and design == "per_command_mldsa44" and side == "{side}"', fmt="{:.1f}", scale=1e-6,
                                        label="RTL simulated", doc=doc)
            n[f"{core}_tagm_{side}"] = c(f"cf_{core}_tagm_{side}", SES, "cycles_median",
                                         f'core == "{core}" and design == "mavlink_tag" and unit == "per message, tag alone, COMMAND_LONG" and side == "{side}"',
                                         fmt="{:.3f}", scale=1e-6, label="RTL simulated", doc=doc)
        for side, num, den in (("vehicle", "hybrid_f1", "classical"), ("ground", "hybrid_f1", "classical"), ("vehicle", "hybrid_f1", "pq_only"),
                               ("ground", "hybrid_f1", "pq_only"), ("vehicle", "kem_auth", "classical"), ("vehicle", "kem_auth", "hybrid_f1")):
            k = f"{core}_r_{num}_{den}_{side}"
            n[k] = rat("cf_" + k, core, side, num, den)
            n[k + "_lo"] = rat("cf_" + k + "_lo", core, side, num, den, "ci95_low")
            n[k + "_hi"] = rat("cf_" + k + "_hi", core, side, num, den, "ci95_high")
    for d in ("classical", "hybrid_f1", "kem_auth"):
        n[f"stack_{d}"] = ses(f"cf_stack_{d}", "cv32e40p", d, "vehicle", "peak_stack_bytes", 1e-3, "{:.1f}")
    n["tag_v"] = c("cf_tag_v", SES, "cycles_median", 'core == "cv32e40p" and design == "mavlink_tag" and unit == "per message, tag alone, COMMAND_LONG" and side == "vehicle"',
                   fmt="{:,.0f}", label="RTL simulated", doc=doc)
    for op, fmt in (("x25519_shared", "{:.2f}"), ("mlkem768_encaps", "{:.2f}"), ("ed25519_verify", "{:.2f}")):
        n[f"cv_{op}"] = c(f"cf_cv_{op}", PRIM, "cycles_median", f'core == "cv32e40p" and operation == "{op}"', fmt=fmt, scale=1e-6, label="RTL simulated", doc=doc)
    n["sign_min"] = c("cf_sign_min", PRIM, "cycles_min", 'core == "cv32e40p" and operation == "mldsa44_sign"', fmt="{:.1f}", scale=1e-6, label="RTL simulated", doc=doc)
    n["sign_max"] = c("cf_sign_max", PRIM, "cycles_max", 'core == "cv32e40p" and operation == "mldsa44_sign"', fmt="{:.1f}", scale=1e-6, label="RTL simulated", doc=doc)
    for d in SESSION_DESIGNS:
        n[f"bytes_{d}"] = c(f"cf_bytes_{d}", SES, "bytes_total", f'core == "cv32e40p" and design == "{d}" and side == "vehicle"',
                            fmt="{:,.0f}", label="RTL simulated", doc=doc)
        for fl in ("f1", "f2", "f3", "f4"):
            if d == "kem_auth" and fl == "f4":
                continue
            n[f"{d}_{fl}"] = c(f"cf_{d}_{fl}", DER, "value", f'core == "cv32e40p" and ratio == "{d}_{fl}_bytes"', fmt="{:,.0f}", label="RTL simulated", doc=doc)
    for img in ("classical", "pq_only", "hybrid_f1", "kem_auth", "per_command_mldsa44", "mavlink_tag"):
        n[f"code_{img}"] = c(f"cf_code_{img}", SIZES, "text_bytes", f'core == "cv32e40p" and variant == "gc" and image == "{img}"', fmt="{:.1f}", scale=1e-3,
                             label="host measured", doc=doc)
    n["t168_hyb"] = c("cf_t168_hyb", TIME, "time_ms", 'core == "cv32e40p" and design == "hybrid_f1" and side == "vehicle" and clock_mhz == 168',
                      fmt="{:.0f}", label="estimated", doc=doc)
    n["t168_cls"] = c("cf_t168_cls", TIME, "time_ms", 'core == "cv32e40p" and design == "classical" and side == "vehicle" and clock_mhz == 168',
                      fmt="{:.0f}", label="estimated", doc=doc)
    n["cv32e40p_pqc_over_tag_vehicle"] = c("cf_cv_pqc_over_tag", DER, "value", 'core == "cv32e40p" and ratio == "pqc_over_tag_vehicle"', fmt="{:.0f}",
                                           label="RTL simulated", doc=doc)
    n["ibex_pqc_over_tag_vehicle"] = c("cf_ibex_pqc_over_tag", DER, "value", 'core == "ibex" and ratio == "pqc_over_tag_vehicle"', fmt="{:.0f}",
                                       label="RTL simulated", doc=doc)
    n["bytes_hyb_over_cls"] = c("cf_bytes_hyb_over_cls", DER, "value", 'core == "cv32e40p" and ratio == "bytes_hyb_over_cls"', fmt="{:.0f}",
                                label="RTL simulated", doc=doc)
    n["core_ratio_hyb"] = c("cf_core_ratio_hyb", DER, "value", 'core == "ibex over cv32e40p" and ratio == "hyb_vehicle"', fmt="{:.2f}",
                            label="RTL simulated", doc=doc)
    PS = "data/predictions_v6_scores.csv"
    n["q_n"] = c("cf_q_n", PS, "id", aggregate="count", label="host measured", doc=doc)
    for vv in ("hit", "between", "miss"):
        n[f"q_{vv}"] = c(f"cf_q_{vv}", PS, "id", f'verdict == "{vv}"', "count", label="host measured", doc=doc)
    # formal
    M4 = "rtlsim/results/ibex_vs_cortex_m4.csv"
    m4q = 'parameter_set in ("ML-KEM-768", "ML-DSA-44") and operation != "sign"'
    n["m4c_lo"] = c("cf_m4c_lo", M4, "ratio_to_clean", m4q, "min", "{:.1f}", label="RTL simulated", doc=doc)
    n["m4c_hi"] = c("cf_m4c_hi", M4, "ratio_to_clean", m4q, "max", "{:.1f}", label="RTL simulated", doc=doc)
    n["m4a_lo"] = c("cf_m4a_lo", M4, "ratio_to_asm", m4q, "min", "{:.1f}", label="RTL simulated", doc=doc)
    n["m4a_hi"] = c("cf_m4a_hi", M4, "ratio_to_asm", m4q, "max", "{:.1f}", label="RTL simulated", doc=doc)
    m4q2 = 'parameter_set in ("ML-KEM-768", "ML-DSA-44")'
    n["m4c_lo2"] = c("cf_m4c_lo2", M4, "ratio_to_clean", m4q2, "min", "{:.1f}", label="RTL simulated", doc=doc)
    n["m4c_hi2"] = c("cf_m4c_hi2", M4, "ratio_to_clean", m4q2, "max", "{:.1f}", label="RTL simulated", doc=doc)
    n["m4a_lo2"] = c("cf_m4a_lo2", M4, "ratio_to_asm", m4q2, "min", "{:.1f}", label="RTL simulated", doc=doc)
    n["m4a_hi2"] = c("cf_m4a_hi2", M4, "ratio_to_asm", m4q2, "max", "{:.1f}", label="RTL simulated", doc=doc)
    FM = "data/flightstack_memory.csv"
    n["fs_flash_lo"] = c("cf_fs_flash_lo", FM, "flash_free_bytes", 'stack == "ardupilot"', "min", "{:.0f}", 1e-3, label="host measured", doc=doc)
    n["fs_flash_hi"] = c("cf_fs_flash_hi", FM, "flash_free_bytes", 'stack == "ardupilot"', "max", "{:.0f}", 1e-3, label="host measured", doc=doc)
    n["fs_ram_lo"] = c("cf_fs_ram_lo", FM, "ram_free_static_bytes", 'stack == "ardupilot"', "min", "{:.0f}", 1e-3, label="host measured", doc=doc)
    n["fs_boards"] = c("cf_fs_boards", FM, "board", 'stack == "ardupilot"', "count", "{:.0f}", label="host measured", doc=doc)
    FS = "data/raw/S15_signature_sizes.csv"
    n["falcon_sig"] = c("cf_falcon_sig", FS, "signature_bytes", 'scheme == "Falcon-512"', fmt="{:,.0f}", label="published", doc=doc)
    n["mldsa_sig"] = c("cf_mldsa_sig", SES, "bytes_total", 'core == "cv32e40p" and design == "per_command_mldsa44" and side == "vehicle"', fmt="{:,.0f}",
                       label="RTL simulated", doc=doc)
    n["x_pair"] = c("cf_x_pair", DER, "value", 'ratio == "x25519_pair_cycles"', fmt="{:.2f}", scale=1e-6, label="RTL simulated", doc=doc)
    n["hyb_minus_pq"] = c("cf_hyb_minus_pq", DER, "value", 'ratio == "hyb_minus_pq_vehicle_cycles"', fmt="{:.2f}", scale=1e-6, label="RTL simulated", doc=doc)
    n["air13"] = c("cf_air13", DER, "value", 'ratio == "sig_field_airtime_ms"', fmt="{:.1f}", label="estimated", doc=doc)
    n["ow_rise"] = c("cf_ow_rise", DER, "value", 'ratio == "ow_rise_signing_ms"', fmt="{:.1f}", label="emulated", doc=doc)
    tq = 'id not in ("Q13", "Q14")'
    n["qt_n"] = c("cf_qt_n", PS, "id", tq, "count", label="host measured", doc=doc)
    for vv in ("hit", "between", "miss"):
        n[f"qt_{vv}"] = c(f"cf_qt_{vv}", PS, "id", tq + f' and verdict == "{vv}"', "count", label="host measured", doc=doc)
    # round 7: Falcon-512 per command (RTL simulated; sizes host measured; Cortex-M4 check emulated)
    FAL, FR = "rtlsim/results/proto_falcon.csv", "rtlsim/results/proto_falcon_ratios.csv"
    for core in ("ibex", "cv32e40p"):
        for op, key, fmt in (("vehicle_verify_command", "v", "{:.2f}"), ("ground_sign_command", "g", "{:.1f}"),
                             ("provisioning_keypair", "kg", "{:.0f}")):
            n[f"fal_{key}_{core}"] = c(f"cf_fal_{key}_{core}", FAL, "cycles_median", f'core == "{core}" and operation == "{op}"',
                                       fmt=fmt, scale=1e-6, label="RTL simulated", doc=doc)
        for op, key in (("vehicle_verify_command", "v"), ("ground_sign_command", "g")):
            q = f'comparison == "Falcon-512 over ML-DSA-44 per command" and core == "{core}" and operation == "{op}"'
            n[f"fal_r{key}_{core}"] = c(f"cf_fal_r{key}_{core}", FR, "ratio", q, fmt="{:.2f}" if key == "v" else "{:.1f}",
                                         label="RTL simulated", doc=doc)
    for op, key in (("vehicle_verify_command", "v"), ("ground_sign_command", "g")):
        n[f"fal_stack_{key}"] = c(f"cf_fal_stack_{key}", FAL, "peak_stack_bytes", f'operation == "{op}"', "max", "{:.1f}", 1e-3,
                                  label="RTL simulated", doc=doc)
    n["fal_code"] = c("cf_fal_code", FAL, "text_bytes_gc_host_measured", 'core == "cv32e40p" and operation == "vehicle_verify_command"',
                      fmt="{:.1f}", scale=1e-3, label="host measured", doc=doc)
    n["fal_bytes"] = c("cf_fal_bytes", FAL, "bytes_per_command", 'core == "cv32e40p" and operation == "vehicle_verify_command"',
                       fmt="{:,.0f}", label="RTL simulated", doc=doc)
    n["fal_sigb"] = c("cf_fal_sigb", FAL, "signature_bytes", 'core == "cv32e40p" and operation == "vehicle_verify_command"',
                      fmt="{:,.0f}", label="RTL simulated", doc=doc)
    QF = "bench/mcu/qemu_results_r7/checks.csv"
    n["m4_levels"] = c("cf_m4_levels", QF, "opt", "fail == 0", "nunique", "{:.0f}", label="emulated", doc=doc)
    n["m4_fail"] = c("cf_m4_fail", QF, "fail", "", "sum", "{:.0f}", label="emulated", doc=doc)
    PS7 = "data/predictions_v7_scores.csv"
    if (ROOT / PS7).exists():
        k7 = {vv: c(f"cf_q7_{vv}", PS7, "id", f'verdict == "{vv}"', "count", label="host measured", doc=doc) for vv in ("hit", "between", "miss")}
        n["r7_disc"] = ("A second set of " + c("cf_q7_n", PS7, "id", aggregate="count", label="host measured", doc=doc)
                        + " predictions for the Falcon-512, burst loss and larger runs was registered later, after design K was added, and scored the same way: "
                        + k7["hit"] + " hit, " + k7["between"] + " fell between and " + k7["miss"] + " missed.")
    # set up of the flights in the loop
    n["sik_kbps"] = c("cf_sik_kbps", SHARED, "value", 'parameter == "sik_air_rate_bps"', fmt="{:.0f}", scale=1e-3, label="published", doc=doc)
    n["clock"] = c("cf_clock", SHARED, "value", 'parameter == "clock_m4_ref_mhz"', fmt="{:.0f}", label="published", doc=doc)
    n["loss"] = c("cf_loss", MA, "value", 'name == "frame_loss"', fmt="{:.2f}", label="assumption", doc=doc)
    n["out_mean"] = c("cf_out_mean", MA, "value", 'name == "outage_mean_s"', fmt="{:.0f}", label="assumption", doc=doc)
    n["sess_to"] = c("cf_sess_to", MA, "value", 'name == "session_timeout_s"', fmt="{:.0f}", label="assumption", doc=doc)
    n["out_a"] = c("cf_out_a", SST, "value", 'name == "outage_window_start_s"', fmt="{:.0f}", label="assumption", doc=doc)
    n["out_b"] = c("cf_out_b", SST, "value", 'name == "outage_window_end_s"', fmt="{:.0f}", label="assumption", doc=doc)
    n["win"] = c("cf_win", RA, "value", 'name == "replay_window_counters"', fmt="{:.0f}", label="assumption", doc=doc)
    return n


PREAMBLE = r"""\documentclass[conference]{IEEEtran}
\pdfsuppressptexinfo=-1
\pdfinfoomitdate=1
\pdftrailerid{}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{url}
\usepackage{cite}
\usepackage{amsmath}
\usepackage{xcolor}
\begin{document}
"""


def authors(anon):
    if anon:
        return r"\author{\IEEEauthorblockN{Anonymous author(s)}\IEEEauthorblockA{Affiliation withheld for review}}"
    return (r"\author{\IEEEauthorblockN{Huda Mueen}" "\n"
            r"\IEEEauthorblockA{\textit{Dept. of Data Science \& AI} \\ \textit{University of Stirling}\\ Ras Al Khaimah, United Arab Emirates \\ hudamueen2407@gmail.com}" "\n"
            r"\and" "\n"
            r"\IEEEauthorblockN{Awaiz Ahmed}" "\n"
            r"\IEEEauthorblockA{\textit{Dept. of Software Engineering} \\ \textit{Al Ain University}\\ Abu Dhabi, United Arab Emirates \\ awaiz42ad@gmail.com}}")


def artifact(anon):
    if anon:
        return "The code, data, logs and scripts are in a public repository whose link is withheld for review."
    return f"The code, data, logs and scripts are public at \\url{{{REPO}}}."


def text(n, s, anon):
    """The paper. n: RTL, formal and set up numbers; s: software in the loop numbers and the text that uses them."""
    meta = "" if anon else "\\pdfinfo{/Author (Huda Mueen; Awaiz Ahmed)}\n"
    return PREAMBLE + meta + r"""
\title{Securing UAV Command and Control Against Quantum Adversaries: Hybrid, KEM Authenticated and Signature Based Post Quantum MAVLink Designs Compared on RISC-V Cores and ArduPilot}
""" + authors(anon) + r"""
\maketitle

\begin{abstract}
Drone flight controllers fielded today may still fly when an attacker can break classical public key cryptography. This measurement study compares seven MAVLink command channel designs under one set of conditions: MAVLink 2 signing, classical (X25519, Ed25519), post quantum only (ML-KEM-768, ML-DSA-44) and hybrid sessions, a session authenticated by pinned static ML-KEM-768 keys (design K), and an ML-DSA-44 or a Falcon-512 signature on every command. In cycle accurate simulation of two open RISC-V cores, the hybrid session costs """ + n["cv32e40p_r_hybrid_f1_classical_vehicle"] + r""" to """ + n["ibex_r_hybrid_f1_classical_vehicle"] + r""" times the vehicle side computation of the classical session and design K """ + n["cv32e40p_r_kem_auth_classical_vehicle"] + r""" to """ + n["ibex_r_kem_auth_classical_vehicle"] + r""" times. Gateways that execute the cryptography in front of ArduPilot in software in the loop, over an emulated telemetry radio, show that """ + s["abstract"].replace("@FALRG@", n["fal_rg_cv32e40p"]) + r""" In ProVerif, a replay cache gives injective agreement on commands only if each counter is checked and recorded in one step, and design K loses key secrecy once ML-KEM alone is broken. """ + artifact(anon) + r"""
\end{abstract}

\section{Introduction}
A small multirotor runs its flight stack on a microcontroller and receives commands over a telemetry radio of tens of kilobits per second. MAVLink 2, the common protocol, offers a per message tag with a pre shared key \cite{mavsign}; without it, commands can be injected from the radio side \cite{kwon18,koubaa19}, and key establishment and endpoint authentication are left to the operator. A pre shared key is not broken by a quantum computer, but one stolen key exposes every session that used it, and a fleet must provision and rotate such keys by hand. A session key exchange removes both problems, but its public key part is what a quantum computer threatens during the years a vehicle stays in service. The replacements are standardised: ML-KEM for key establishment \cite{fips203} and ML-DSA for signatures \cite{fips204}.

This is a measurement study, and its building blocks are known: design K follows KEMTLS with pre distributed keys and post quantum WireGuard \cite{kemtlspdk21,pqwg21}, the hybrid key derivation follows hybrid KEM combiners such as X-Wing \cite{xwing24}, and the replay cache is the sliding receive window of IPsec \cite{rfc4303}. Hyoung et al.\ argue from post quantum TLS handshakes over an emulated drone radio that, after the handshake, commands should carry only a symmetric tag, but derive rather than measure the per command cost \cite{hyoung26}. Missing is a comparison of complete designs on the same core, link and flight stack, including what the replay rule does to commands.

This paper contributes:
(1) executed baselines of seven command channel designs on two open RISC-V core designs in cycle accurate register transfer level (RTL) simulation, with correctness checks, intervals over """ + n["runs"] + r""" runs, stack and code size, under one compiler and pinned libraries (Section~\ref{sec:rtl});
(2) a gateway emulation in front of ArduPilot software in the loop (SITL) that executes the handshakes, tags, signatures and replay rules on paired seeds, also under burst loss and over 100 missions per configuration (Section~\ref{sec:sitl});
(3) ProVerif models of the hybrid and the KEM authenticated sessions and of replay rules that accept out of order delivery, with the bounds of each model (Section~\ref{sec:formal}).
Every number in this paper is read by script from a committed result file.

\section{Related work}
\label{sec:rw}
Primitives are benchmarked on Cortex-M4 with pqm4 \cite{pqm4}, with stack optimised Dilithium \cite{greconici21} and with RISC-V extensions \cite{alkim20,fritzmann20}. Post quantum TLS has been measured on embedded clients \cite{burstinghaus20} and under packet loss \cite{paquin20,sikeridis20}; KEMTLS \cite{kemtls20,kemtlspdk21}, post quantum WireGuard and post quantum Noise \cite{pqwg21,pqnoise22} authenticate by encapsulation instead of signatures. For drones, MAVSec encrypts MAVLink \cite{mavsec19}, Ahmed et al.\ combine two ML-KEM-768 encapsulations with ML-DSA-65 certificates and compute radio times without a flight stack \cite{ahmed26}, and de Meneses et al.\ verify a post quantum EDHOC variant with estimated costs \cite{meneses26}; for vehicle to vehicle messages, frame loss can decide practicality \cite{twardokus24}. Table~\ref{tab:rw} compares the closest drone and post quantum protocol studies by method, not figures, because platforms and links differ.

\begin{table*}[t]
\centering
\caption{Closest prior work and this paper (as recorded from each source)}
\label{tab:rw}
\setlength{\tabcolsep}{2pt}
\footnotesize
\begin{tabular}{llllll}
\toprule
Work & Platform & Link and stack & Per command cost & Availability & Formal check \\
\midrule
\cite{hyoung26} & x86 laptop & emulated UAV radio, TLS 1.3 & derived, not measured & not reported & none reported \\
\cite{pqwg21} & virtual machines & virtual network, WireGuard & not reported & not reported & Tamarin, with replay \\
\cite{ahmed26} & x86 laptop & none; SiK radio times computed & not reported & not reported & proof on paper \\
\cite{meneses26} & modelled Cortex-M4 & UAV, EDHOC variant, computed delays & not reported & not reported & Tamarin \\
This paper & two RISC-V cores (RTL) & emulated SiK radio, ArduPilot SITL & executed (RTL) & measured per rule & ProVerif \\
\bottomrule
\end{tabular}
\end{table*}

\section{Threat model and designs}
\label{sec:design}
\emph{Threat model.} The attacker controls the radio: it reads, drops, delays, reorders and injects frames and replays old ones, and it may hold a quantum computer during the service life of the vehicle. Endpoints, their long term keys and the flight stack are trusted; side channels, jamming beyond the modelled loss and outages, and the confidentiality of commands are out of scope. So is resource exhaustion: an injected first flight makes the vehicle compute for """ + s["dos_k"] + r"""~ms (design K) or """ + s["dos_h"] + r"""~ms (hybrid) at the applied clock before anything is authenticated, so a deployment needs rate limiting. The goals are mutual authentication of the session endpoints, secrecy of the session key that keys the tags, and injective agreement on commands: every accepted command was sent by the ground station in that session and is accepted at most once. Per message protection stays the MAVLink 2 tag, SHA-256 over key, frame and counter truncated to 48 bits \cite{mavsign}, so a forged frame succeeds with probability $2^{-48}$, and every attempt must be sent over the radio.

\emph{Session designs.} All sessions end with the MAVLink 2 signing field of 13~B per message, keyed by the session key. \emph{Classical}: X25519 key exchange, Ed25519 signatures by both sides over the transcript and both identities, key confirmation tags. \emph{Post quantum only}: ML-KEM-768 and ML-DSA-44 in the same roles. \emph{Hybrid} (proposed): X25519 and ML-KEM-768 together, the session key derived from both secrets and a transcript hash, ML-DSA-44 signatures by both sides; a variant in which only the ground station signs leaves the vehicle unauthenticated in our model, so the vehicle signs too (mutual signing). \emph{KEM authenticated} (design K): each side holds the other's static ML-KEM-768 key; the ground station sends an X25519 share, an ephemeral ML-KEM-768 key and an encapsulation to the vehicle's static key, the vehicle answers with its share, a ciphertext to the ephemeral key, an encapsulation to the ground station's static key and a confirmation tag, and the ground station confirms; there are no signatures. Fig.~\ref{fig:flows} shows the flights of the hybrid session and of design K with their payload bytes; the classical and post quantum only sessions carry """ + n["bytes_classical"] + r"""~B and """ + n["bytes_pq_only"] + r"""~B in four flights, without MAVLink framing.

\begin{figure}[t]
\centering
\includegraphics[width=\columnwidth]{fig_flows.pdf}
\caption{Handshake flights of the hybrid session with mutual signing (left) and of design K (right), with their bytes as built; pink arrows carry ML-DSA-44 signatures.}
\label{fig:flows}
\end{figure}

\emph{Baselines without a session.} \emph{Signing as shipped}: a provisioned key, no handshake. \emph{Signature per command}: an ML-DSA-44 or a Falcon-512 signature on every command, verified by the vehicle; """ + s["pqsig_def"] + r"""

\emph{Replay rules.} MAVLink 2 signing carries a 48 bit timestamp per stream, and its \emph{published} rule accepts a frame whose timestamp exceeds the last one accepted on that stream \cite{mavsign}; our gateways put a per session counter into that field and apply the same rule, so gaps are allowed. """ + s["rules"] + r""" The \emph{replay cache} accepts any counter not yet accepted within a window of """ + n["win"] + r""" counters, the default receive window of IPsec \cite{rfc4303}.


\section{Method}
\label{sec:method}
\emph{RTL simulation.} Ibex in its small configuration \cite{ibex} and CV32E40P \cite{cv32e40p}, both RV32IMC without caches or wait states, are simulated cycle accurately with Verilator. One firmware image per design runs the vehicle and the ground side, each step timed with the cycle counter, """ + n["runs"] + r""" runs per session image with a fixed seed block (""" + n["runs_tag"] + r""" for the deterministic tag image); every run checks that both sides derive the same key, that all signatures and tags verify, and hash known answers; medians carry 95\% intervals over runs. Libraries are pinned and unmodified: mlkem-native \cite{mlkemnative}, mldsa-native \cite{mldsanative}, Monocypher \cite{monocypher} and the padded Falcon-512 of liboqs \cite{liboqs,falcon}, all portable C, compiled with one compiler at \texttt{-O3}; neither core has a floating point unit, so Falcon runs its integer emulation of floating point. Peak stack is measured by stack painting and includes the harness; code size is the text section of each image with unused sections removed, both sides and the harness included.

\emph{Gateway emulation with ArduPilot SITL.} ArduPilot Copter 4.7.2 \cite{ardupilot} flies a scripted mission of about """ + s["flight_s"] + r"""~s (take off, two legs, land) with its built in vehicle model; the ground station sends one acknowledged COMMAND\_LONG message per second. A relay emulates a SiK class telemetry radio of """ + n["sik_kbps"] + r"""~kbit/s with independent frame loss of """ + n["loss"] + r""", link layer retransmission that can deliver frames out of order, and one outage per mission starting """ + n["out_a"] + r"""--""" + n["out_b"] + r"""~s after arming with an exponential duration of mean """ + n["out_mean"] + r"""~s; an outage longer than """ + n["sess_to"] + r"""~s tears the session down. A gateway pair between the ground station, the relay and the flight stack executes the handshake, the tags and the replay rule with the same algorithms (Python cryptography and host builds of the same libraries); the flight stack itself runs unmodified and never executes the cryptography. Vehicle side operations are released after a delay equal to their Ibex cycles at """ + n["clock"] + r"""~MHz, the clock of a Cortex-M4 flight controller, fixed from the first runs before the flights (for design K, flown later, from the medians of all runs); ground side compute runs at host speed. """ + s["method"] + r"""

\emph{Formal models.} ProVerif \cite{proverif} checks secrecy, agreement and reachability under a Dolev Yao attacker with perfect abstract primitives and unbounded sessions; binding properties of the KEMs are not analysed. Session models carry one command, a rekey and a further command per session; replay cache models carry three commands per key; the bounded window is modelled on the command layer for a window of two counters, not the """ + n["win"] + r""" flown. Rekey grace periods, counter wrap and timestamps are not modelled. Breaking a component is modelled by giving its secrets to the attacker.

\emph{Discipline.} Of """ + n["qt_n"] + r""" technical predictions hashed before the runs and scored by script under the less favourable reading, """ + n["qt_hit"] + r""" hit, """ + n["qt_between"] + r""" fell between and """ + n["qt_miss"] + r""" missed; the thresholds were broad, and design K was added after registration. """ + n.get("r7_disc", "") + r"""

\section{Executed baselines on core designs}
\label{sec:rtl}
Table~\ref{tab:rtl} gives the cost of one session start and of one command. On CV32E40P the hybrid session costs """ + n["cv32e40p_r_hybrid_f1_classical_vehicle"] + r"""$\times$ [""" + n["cv32e40p_r_hybrid_f1_classical_vehicle_lo"] + r""", """ + n["cv32e40p_r_hybrid_f1_classical_vehicle_hi"] + r"""] the classical vehicle side, and on Ibex """ + n["ibex_r_hybrid_f1_classical_vehicle"] + r"""$\times$ [""" + n["ibex_r_hybrid_f1_classical_vehicle_lo"] + r""", """ + n["ibex_r_hybrid_f1_classical_vehicle_hi"] + r"""]. Against the post quantum only session the hybrid costs """ + n["cv32e40p_r_hybrid_f1_pq_only_vehicle"] + r"""$\times$ [""" + n["cv32e40p_r_hybrid_f1_pq_only_vehicle_lo"] + r""", """ + n["cv32e40p_r_hybrid_f1_pq_only_vehicle_hi"] + r"""] on the vehicle side and """ + n["cv32e40p_r_hybrid_f1_pq_only_ground"] + r"""$\times$ on the ground side of CV32E40P. The two designs differ by two X25519 operations, a fixed """ + n["x_pair"] + r"""~M cycles, yet their measured medians differ by only """ + n["hyb_minus_pq"] + r"""~M: ML-DSA-44 signing repeats with rejection and took """ + n["sign_min"] + r""" to """ + n["sign_max"] + r"""~M cycles per signature, so the medians of the signing designs are noisy, and the sums of primitive medians drawn in Fig.~\ref{fig:rtl} exceed the measured session medians. With Monocypher, one X25519 multiplication (""" + n["cv_x25519_shared"] + r"""~M cycles on CV32E40P) costs more than an ML-KEM-768 encapsulation (""" + n["cv_mlkem768_encaps"] + r"""~M), and an Ed25519 verification """ + n["cv_ed25519_verify"] + r"""~M; this is a property of one portable C library designed for size, and a faster classical library would raise every ratio over the classical session.
""" + rtl_table(n) + r"""
\begin{figure}[t]
\centering
\includegraphics[width=\columnwidth]{fig_rtl.pdf}
\caption{Vehicle side cycles of one session start on CV32E40P by primitive (RTL simulated). Bars are sums of primitive medians, which exceed the measured medians of the signing designs; the whisker is the bar total if its one signature took the fastest or the slowest ML-DSA-44 signing observed; the dot is the measured session median.}
\label{fig:rtl}
\end{figure}

Design K avoids both ML-DSA-44 operations: on CV32E40P its vehicle side costs """ + n["cv32e40p_r_kem_auth_classical_vehicle"] + r"""$\times$ the classical session and """ + n["cv32e40p_r_kem_auth_hybrid_f1_vehicle"] + r"""$\times$ [""" + n["cv32e40p_r_kem_auth_hybrid_f1_vehicle_lo"] + r""", """ + n["cv32e40p_r_kem_auth_hybrid_f1_vehicle_hi"] + r"""] the hybrid one, it needs """ + n["stack_kem_auth"] + r"""~kB of stack against """ + n["stack_hybrid_f1"] + r"""~kB for the hybrid (""" + n["stack_classical"] + r"""~kB classical), and it carries """ + n["bytes_kem_auth"] + r"""~B in three flights against """ + n["bytes_hybrid_f1"] + r"""~B for the hybrid session, which carries """ + n["bytes_hyb_over_cls"] + r"""$\times$ the bytes of the classical handshake. Code for both sides and the harness grows from """ + n["code_classical"] + r"""~kB (classical) to """ + n["code_hybrid_f1"] + r"""~kB (hybrid) and """ + n["code_kem_auth"] + r"""~kB (design K). The """ + n["fs_boards"] + r""" ArduPilot builds we measured leave """ + n["fs_flash_lo"] + r""" to """ + n["fs_flash_hi"] + r"""~kB of flash and at least """ + n["fs_ram_lo"] + r"""~kB of static RAM free (host measured from linker output), so the code fits, but a """ + n["stack_hybrid_f1"] + r"""~kB stack would need a thread of its own or a stack optimised signer \cite{greconici21}; a vehicle only image was not measured. After the handshake a command costs a tag check of """ + n["tag_v"] + r""" cycles on a COMMAND\_LONG (the tag alone, without parsing); verifying an ML-DSA-44 signature on the same frame costs """ + n["cv32e40p_pqc_over_tag_vehicle"] + r"""$\times$ as much on CV32E40P, and signing it on the ground side about twice that. A Falcon-512 signature (""" + n["fal_sigb"] + r"""~B) is verified in """ + n["fal_v_cv32e40p"] + r"""~M cycles on CV32E40P, """ + n["fal_rv_cv32e40p"] + r"""$\times$ the ML-DSA-44 verification, with """ + n["fal_stack_v"] + r"""~kB of stack, but signing with emulated floating point takes """ + n["fal_g_cv32e40p"] + r"""~M cycles, """ + n["fal_rg_cv32e40p"] + r"""$\times$ ML-DSA-44 signing; on an emulated Cortex-M4 (QEMU, functional only, no cycle counts) the same code signs, verifies and rejects altered input at all """ + n["m4_levels"] + r""" optimisation levels tried. Ibex needs """ + n["core_ratio_hyb"] + r"""$\times$ the cycles of CV32E40P for the same handshake, so cycle counts do not transfer between cores.

\section{Gateway emulation with ArduPilot SITL}
\label{sec:sitl}
""" + s["section"] + r"""

\section{Formal results}
\label{sec:formal}
""" + s["formal"] + r"""

\section{Discussion and limitations}
For streamed commands the results support a session: its post quantum cost is paid once, and the per command cost stays that of the shipped tag. Where both identities can be pinned, design K is cheaper but rests on ML-KEM alone; the hybrid session keeps the classical component as a guard against a flaw in ML-KEM, while its authentication rests on ML-DSA-44. """ + s["disc"].replace("@FALRG@", n["fal_rg_cv32e40p"]).replace("@FALSIG@", n["fal_bytes"]).replace("@MLDSASIG@", n["mldsa_sig"]) + r"""

\emph{Threats to validity.} (i) Cycles come from two open core designs with single cycle memories, applied at a Cortex-M4 clock; Cortex-M flight controllers have flash wait states, caches and other multipliers, and an earlier run of portable C code on Ibex took """ + n["m4c_lo2"] + r""" to """ + n["m4c_hi2"] + r""" times the published portable C cycles on Cortex-M4 and """ + n["m4a_lo2"] + r""" to """ + n["m4a_hi2"] + r""" times its assembly for ML-KEM-768 and ML-DSA-44; stack optimised signing \cite{greconici21} or RISC-V extensions \cite{alkim20,fritzmann20} would change the figures, and the Cortex-M4 check of Falcon-512 is functional only. (ii) One classical library was measured, and it favours the post quantum designs. (iii) The cryptography runs in gateways, not in the flight stack, so the scheduling load of a handshake on the flight controller is not measured; vehicle compute is a delay applied per event without a busy processor, and the host was slower than that delay for a small share of tags. """ + s.get("thr", r"""(iv) The radio is an emulation with independent frame loss and one scripted outage per mission, real loss is bursty, and the strict rule results rest on about a dozen outage triggered events. (v) Twenty missions per configuration, a bootstrap over missions that may under cover, and no correction for the several paired comparisons.""") + r""" (vi) The formal models use perfect primitives and small bounds (Section~\ref{sec:method}). Next, the baselines should be repeated on Cortex-M boards with the vehicle side inside the flight stack and a real radio.

\section{Conclusion}
""" + s["conclusion"].replace("@FALRG@", n["fal_rg_cv32e40p"]).replace("{hyb_lo}", n["cv32e40p_r_hybrid_f1_classical_vehicle"]).replace("{hyb_hi}", n["ibex_r_hybrid_f1_classical_vehicle"]) + r"""

\bibliographystyle{IEEEtran}
\bibliography{references}
\end{document}
"""


def flights_rows(n):
    rows = []
    for d in SESSION_DESIGNS:
        f4 = n.get(d + "_f4", "--")
        rows.append(f"{DESIGN_NAMES[d] if d != 'kem_auth' else 'KEM auth. (K)'} & {n[d + '_f1']} & {n[d + '_f2']} & {n[d + '_f3']} & {f4} & {n['bytes_' + d]} \\\\")
    return "\n".join(rows)


def rtl_table(n):
    rows = [("MAVLink 2 tag$^{a}$", n["ibex_tagm_vehicle"], n["cv32e40p_tagm_vehicle"], n["ibex_tagm_ground"], n["cv32e40p_tagm_ground"], n["code_mavlink_tag"]),
            ("Classical session", n["ibex_classical_vehicle"], n["cv32e40p_classical_vehicle"], n["ibex_classical_ground"], n["cv32e40p_classical_ground"], n["code_classical"]),
            ("PQ only session", n["ibex_pq_only_vehicle"], n["cv32e40p_pq_only_vehicle"], n["ibex_pq_only_ground"], n["cv32e40p_pq_only_ground"], n["code_pq_only"]),
            ("Hybrid session", n["ibex_hybrid_f1_vehicle"], n["cv32e40p_hybrid_f1_vehicle"], n["ibex_hybrid_f1_ground"], n["cv32e40p_hybrid_f1_ground"], n["code_hybrid_f1"]),
            ("KEM auth.\\ session (K)", n["ibex_kem_auth_vehicle"], n["cv32e40p_kem_auth_vehicle"], n["ibex_kem_auth_ground"], n["cv32e40p_kem_auth_ground"], n["code_kem_auth"]),
            ("ML-DSA-44 per command$^{b}$", n["ibex_pqc_vehicle"], n["cv32e40p_pqc_vehicle"], n["ibex_pqc_ground"], n["cv32e40p_pqc_ground"], n["code_per_command_mldsa44"]),
            ("Falcon-512 per command$^{b,c}$", n["fal_v_ibex"], n["fal_v_cv32e40p"], n["fal_g_ibex"], n["fal_g_cv32e40p"], n["fal_code"])]
    body = "\n".join(f"{a} & {b} & {c} & {d} & {e} & {f} \\\\" for a, b, c, d, e, f in rows)
    return r"""\begin{table}[t]
\centering
\caption{Executed baselines: million cycles per unit (RTL simulated, medians of """ + n["runs"] + r""" runs, """ + n["runs_tag"] + r""" for the tag row) and code size on CV32E40P (host measured)}
\label{tab:rtl}
\setlength{\tabcolsep}{2.5pt}
\begin{tabular}{lrrrrr}
\toprule
 & \multicolumn{2}{c}{Vehicle} & \multicolumn{2}{c}{Ground} & Code \\
Design & Ibex & CV32E40P & Ibex & CV32E40P & (kB) \\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}

\smallskip\footnotesize Session rows: one session start. $^{a}$ check (vehicle) and generation (ground) of one tag over a COMMAND\_LONG frame. $^{b}$ verification (vehicle) and signing (ground) of one command. $^{c}$ padded Falcon-512 with integer emulated floating point; key pair made once.
\end{table}
"""


SS = "sitl/results_r6/summary.csv"
SP = "sitl/results_r6/paired.csv"
SR = "sitl/results_r6/rejections.csv"
SC = "sitl/results_r6/comparison.csv"
SD = "sitl/results_r6/deadline_sweep.csv"
SH = "sitl/results_r6/host_compute.csv"
SO = "sitl/results_r6/reorder.csv"
MO = "mission/results/replay_outage_sweep.csv"
CFGS_ALL = [("none", "No authentication"), ("signing", "MAVLink 2 signing as shipped"), ("classical", "Classical session"),
            ("hybrid_published", "Hybrid, published rule"), ("hybrid_strict", "Hybrid, strict rule, new handshake"),
            ("hybrid_strict_inband", "Hybrid, strict rule, in session"), ("hybrid_cache", "Hybrid, replay cache"),
            ("kem_auth", "Design K, published rule"), ("pqsig_real", "ML-DSA-44 per command"), ("pqsig_counter", "ML-DSA-44 per command, counter")]
# paired comparisons drawn in Fig. 4: (config, minus, label)
PAIRS_ALL = [("hybrid_strict", "hybrid_published", "strict, new handshake $-$ published"),
             ("hybrid_strict_inband", "hybrid_published", "strict, in session $-$ published"),
             ("pqsig_counter", "pqsig_real", "ML-DSA-44 with counter $-$ without"),
             ("hybrid_cache", "hybrid_published", "cache $-$ published"), ("hybrid_published", "classical", "hybrid $-$ classical"),
             ("hybrid_published", "none", "hybrid $-$ none"), ("kem_auth", "classical", "design K $-$ classical")]
SM = "sitl/results_r6/paired_missed.csv"
S7S = "sitl/results_r7/summary.csv"
S7P = "sitl/results_r7/paired_missed.csv"


def _present():
    import pandas as pd
    s = pd.read_csv(ROOT / SS)
    cf = set(s.config)
    if (ROOT / SM).exists():
        p = pd.read_csv(ROOT / SM)
        pairs = set(zip(p.config, p.minus_config))
    else:
        p = pd.read_csv(ROOT / SP)
        pairs = set(zip(p.config, p.minus_config))
    return [x for x in CFGS_ALL if x[0] in cf], [x for x in PAIRS_ALL if (x[0], x[1]) in pairs]


CFGS, PAIRS = _present()


def sitl_numbers(c, doc):
    """Software in the loop numbers, and the text that uses them."""
    q = 'profile == "sik" and config == "{k}" and metric == "{m}"'
    keys = {k for k, _ in CFGS}
    missed = (ROOT / SM).exists()

    def v(cid, k, m, col="value", fmt="{:.3f}", label="SITL measured", scale=1.0):
        return c(cid, SS, col, q.format(k=k, m=m), fmt=fmt, label=label, scale=scale, doc=doc)
    t = {}
    for k, _ in CFGS:
        t[f"{k}_av"] = v(f"cs_{k}_av", k, "availability_rt_all")
        t[f"{k}_av_lo"] = v(f"cs_{k}_av_lo", k, "availability_rt_all", "ci_lo")
        t[f"{k}_av_hi"] = v(f"cs_{k}_av_hi", k, "availability_rt_all", "ci_hi")
        if k != "none":
            t[f"{k}_lat"] = v(f"cs_{k}_lat", k, "added_latency_rt_ms", fmt="{:.1f}")
        if k in ("classical", "hybrid_published", "hybrid_strict", "hybrid_strict_inband", "hybrid_cache", "kem_auth"):
            t[f"{k}_hs"] = v(f"cs_{k}_hs", k, "handshake_median_s", fmt="{:.2f}", label="emulated")
    t["n_miss"] = c("cs_n_miss", SS, "value", 'profile == "sik" and metric == "missions_completed"', "min", "{:.0f}", label="SITL measured", doc=doc)
    t["cmd_min"] = c("cs_cmd_min", SS, "value", 'profile == "sik" and metric == "commands"', "min", "{:.0f}", label="SITL measured", doc=doc)
    t["cmd_max"] = c("cs_cmd_max", SS, "value", 'profile == "sik" and metric == "commands"', "max", "{:.0f}", label="SITL measured", doc=doc)

    def pdiff(cid, a, b, col="difference", fmt="{:+.4f}", scale=1.0):
        return "\\mbox{" + c(cid, SP, col, f'profile == "sik" and config == "{a}" and minus_config == "{b}" and metric == "availability_rt_all"',
                             fmt=fmt, label="SITL measured", scale=scale, doc=doc) + "}"
    t["strict_loss"] = pdiff("cs_strict_loss", "hybrid_strict", "hybrid_published", fmt="{:.3f}", scale=-1.0)
    t["strict_loss_lo"] = pdiff("cs_strict_loss_lo", "hybrid_strict", "hybrid_published", "ci_hi", fmt="{:.3f}", scale=-1.0)
    t["strict_loss_hi"] = pdiff("cs_strict_loss_hi", "hybrid_strict", "hybrid_published", "ci_lo", fmt="{:.3f}", scale=-1.0)

    def rj(cid, k, reason, scope="stream commands not acknowledged within 0.5 s", label="SITL measured"):
        return c(cid, SR, "count", f'profile == "sik" and config == "{k}" and scope == "{scope}" and reason == "{reason}"',
                 fmt="{:.0f}", label=label, doc=doc)
    t["strict_nosession"] = rj("cs_strict_nosession", "hybrid_strict", "no_session")
    t["strict_ahead"] = rj("cs_strict_ahead", "hybrid_strict", "rejected_ahead_of_next")
    t["pub_late"] = rj("cs_pub_late", "hybrid_published", "rejected_late_or_duplicate")
    t["sign_nack"] = rj("cs_sign_nack", "signing", "not_acknowledged_by_vehicle")
    t["resync"] = rj("cs_resync", "hybrid_strict", "all triggers", "resynchronisations (strict rule)", "emulated")
    t["resync_gu"] = rj("cs_resync_gu", "hybrid_strict", "ground_give_up", "resynchronisations (strict rule)", "emulated")
    t["reorder_depth"] = c("cs_reorder_depth", SO, "max_reorder_depth", 'profile == "sik"', "max", "{:.0f}", label="emulated", doc=doc)
    for dl in (0.55, 0.75, 1.0):
        t[f"pq_dl_{dl}"] = c(f"cs_pq_dl_{str(dl).replace('.', '')}", SD, "availability_rt_all", f'profile == "sik" and config == "pqsig_real" and deadline_s == {dl}',
                             fmt="{:.3f}", label="SITL measured", doc=doc)
    DL = "sitl/results_r6/delays.csv"
    t["pq_delay"] = c("cs_pq_delay", DL, "delay_ms", 'name == "mldsa44_verify_command" and core == "ibex"', fmt="{:.0f}", label="estimated", doc=doc)
    t["dos_k"] = c("cs_dos_k", DL, "delay_ms", 'name == "kem_auth_vehicle_f2" and core == "ibex"', fmt="{:.0f}", label="estimated", doc=doc)
    t["dos_h"] = c("cs_dos_h", DL, "delay_ms", 'name == "hybrid_vehicle_f2" and core == "ibex"', fmt="{:.0f}", label="estimated", doc=doc)
    tq = 'core == "ibex" and name in ("tag_check", "tag_make")'
    t["tagd_lo"] = c("cs_tagd_lo", DL, "delay_ms", tq, "min", "{:.2f}", label="estimated", doc=doc)
    t["tagd_hi"] = c("cs_tagd_hi", DL, "delay_ms", tq, "max", "{:.2f}", label="estimated", doc=doc)
    t["flight_s"] = c("cs_flight_s", "sitl/results_r6/missions.csv", "flight_s", 'profile == "sik"', "median", "{:.0f}", label="SITL measured", doc=doc)
    vq = 'profile == "sik" and operation == "vehicle_tag"'
    t["hx_tag"] = c("cs_hx_tag", SH, "host_exceeds_rtl_delay", vq, "sum", "{:,.0f}", label="host measured", doc=doc)
    t["hx_tag_n"] = c("cs_hx_tag_n", SH, "count", vq, "sum", "{:,.0f}", label="host measured", doc=doc)
    t["hx_tag_max"] = c("cs_hx_tag_max", SH, "host_exceeds_rtl_delay", vq, "max", "{:,.0f}", label="host measured", doc=doc)
    t["air13"] = c("cs_air13", DER, "value", 'ratio == "sig_field_airtime_ms"', fmt="{:.1f}", label="estimated", doc=doc)
    t["ow_rise"] = c("cs_ow_rise", DER, "value", 'ratio == "ow_rise_signing_ms"', fmt="{:.1f}", label="emulated", doc=doc)

    MPM = "sitl/results_r6/missed_per_mission.csv"
    RS = "sitl/results_r6/session_restarts.csv"
    for k, _ in CFGS:
        t[f"{k}_mpm"] = c(f"cs_{k}_mpm", MPM, "missed", f'profile == "sik" and config == "{k}"', "mean", "{:.2f}", label="SITL measured", doc=doc)

    def md(cid, a, b, col="difference", fmt="{:+.2f}"):
        return "\\mbox{" + c(cid, SM, col, f'profile == "sik" and config == "{a}" and minus_config == "{b}"', fmt=fmt, label="SITL measured", doc=doc) + "}"
    for a, b in (("hybrid_strict", "hybrid_published"), ("hybrid_strict_inband", "hybrid_published"), ("hybrid_strict_inband", "hybrid_strict"),
                 ("hybrid_cache", "hybrid_published"), ("hybrid_published", "none"), ("hybrid_published", "classical"),
                 ("kem_auth", "classical"), ("pqsig_counter", "pqsig_real")):
        if not (a in keys and b in keys):
            continue
        k_ = f"m_{a}_{b}"
        t[k_] = md("cs_" + k_, a, b)
        t[k_ + "_lo"] = md("cs_" + k_ + "_lo", a, b, "ci_lo")
        t[k_ + "_hi"] = md("cs_" + k_ + "_hi", a, b, "ci_hi")
        t[k_ + "_n"] = md("cs_" + k_ + "_n", a, b, "missions_differing", "{:.0f}")
    t["rs_strict"] = c("cs_rs_strict", RS, "missions_with_teardown_or_rehandshake", 'profile == "sik" and config == "hybrid_strict"', fmt="{:.0f}", label="emulated", doc=doc)
    t["rs_pub"] = c("cs_rs_pub", RS, "missions_with_teardown_or_rehandshake", 'profile == "sik" and config == "hybrid_published"', fmt="{:.0f}", label="emulated", doc=doc)
    if "hybrid_strict_inband" in keys:
        t["resync_in"] = rj("cs_resync_in", "hybrid_strict_inband", "all triggers", "resynchronisations (strict rule)", "emulated")

    # round 7: Falcon-512 per command (falcon20), burst loss (burst20) and the larger set (large100); sitl/results_r7/
    r7 = (ROOT / S7S).exists()
    if r7:
        def v7(cid, st, k, m, col="value", fmt="{:.3f}", label="SITL measured"):
            return c(cid, S7S, col, f'set == "{st}" and config == "{k}" and metric == "{m}"', fmt=fmt, label=label, doc=doc)

        def p7(cid, st, a, b, col="difference", fmt="{:+.2f}"):
            return "\\mbox{" + c(cid, S7P, col, f'set == "{st}" and config == "{a}" and minus_config == "{b}"', fmt=fmt,
                                  label="SITL measured", doc=doc) + "}"
        for k in ("pqsig_falcon", "pqsig_falcon_counter"):
            for m, key, fmt in (("availability_rt_all", "av", "{:.3f}"), ("availability_rt_all_1s", "av1", "{:.3f}"),
                                ("added_latency_rt_ms", "lat", "{:.1f}"), ("missed_per_mission", "mpm", "{:.2f}")):
                t[f"{k}_{key}"] = v7(f"cs7_{k}_{key}", "falcon20", k, m, fmt=fmt)
            t[f"{k}_av_lo"] = v7(f"cs7_{k}_av_lo", "falcon20", k, "availability_rt_all", "ci_lo")
            t[f"{k}_av_hi"] = v7(f"cs7_{k}_av_hi", "falcon20", k, "availability_rt_all", "ci_hi")
        t["pqsig_real_av1"] = c("cs7_pqsig_real_av1", SD, "availability_rt_all", 'profile == "sik" and config == "pqsig_real" and deadline_s == 1.0',
                                fmt="{:.3f}", label="SITL measured", doc=doc)
        for st, a, b in (("falcon20", "pqsig_falcon", "pqsig_real"), ("falcon20", "pqsig_falcon", "hybrid_published"),
                         ("falcon20", "pqsig_falcon_counter", "pqsig_falcon"),
                         ("burst20", "hybrid_strict", "hybrid_published"), ("burst20", "hybrid_strict_inband", "hybrid_published"),
                         ("burst20", "hybrid_cache", "hybrid_published"), ("burst20", "pqsig_falcon", "hybrid_published"),
                         ("burst20", "pqsig_real", "hybrid_published"), ("burst20", "hybrid_published", "none"),
                         ("large100", "hybrid_strict", "hybrid_published"), ("large100", "hybrid_strict_inband", "hybrid_published"),
                         ("large100", "hybrid_cache", "hybrid_published"), ("large100", "hybrid_published", "none"),
                         ("large100", "kem_auth", "hybrid_published"), ("large100", "pqsig_falcon", "hybrid_published")):
            k_ = f"{st}_{a}_{b}"
            if not len(__import__("pandas").read_csv(ROOT / S7P).query(f'set == "{st}" and config == "{a}" and minus_config == "{b}"')):
                continue
            t[k_] = p7("cs7_" + k_, st, a, b)
            t[k_ + "_lo"] = p7("cs7_" + k_ + "_lo", st, a, b, "ci_lo")
            t[k_ + "_hi"] = p7("cs7_" + k_ + "_hi", st, a, b, "ci_hi")
        t["fal_delay"] = c("cs7_fal_delay", "sitl/results_r7/delays.csv", "delay_ms", 'name == "falcon512_verify_command" and core == "ibex"',
                           "max", "{:.1f}", label="estimated", doc=doc)
        t["fal_sig_b"] = c("cs7_fal_sig_b", "rtlsim/results/proto_falcon.csv", "signature_bytes", 'core == "ibex" and operation == "vehicle_verify_command"',
                           fmt="{:.0f}", label="RTL simulated", doc=doc)
        t["fal_sign_host"] = c("cs7_fal_sign_host", "sitl/results_r7/host_compute.csv", "host_mean_ms",
                               'set == "falcon20" and config == "pqsig_falcon" and operation == "ground_sign_command"', "mean", "{:.1f}",
                               label="host measured", doc=doc)
        t["n100"] = c("cs7_n100", S7S, "value", 'set == "large100" and metric == "missions"', "min", "{:.0f}", label="SITL measured", doc=doc)
        t["n20b"] = c("cs7_n20b", S7S, "value", 'set == "burst20" and metric == "missions"', "min", "{:.0f}", label="SITL measured", doc=doc)
        t["burst_frames"] = c("cs7_burst_frames", "sitl/settings_r7.csv", "value", 'name == "burst_mean_frames"', fmt="{:.0f}", label="assumption", doc=doc)
        B7 = "sitl/results_r7/burst_loss.csv"
        if (ROOT / B7).exists():
            import pandas as pd
            bl = pd.read_csv(ROOT / B7)
            t["burst_lost"] = c("cs7_burst_lost", B7, "burst_lost_frames", "", "sum", "{:,.0f}", label="emulated", doc=doc)
            t["burst_frames_sent"] = c("cs7_burst_frames_sent", B7, "frames", "", "sum", "{:,.0f}", label="emulated", doc=doc)
            t["burst_rate"] = f"{bl.burst_lost_frames.sum() / bl.frames.sum():.3f}"
        L7 = "sitl/results_r7/loss_change.csv"
        if (ROOT / L7).exists():
            for k in ("hybrid_published", "pqsig_real", "pqsig_falcon", "hybrid_strict"):
                t[f"chg_{k}"] = "\\mbox{" + c(f"cs7_chg_{k}", L7, "difference", f'config == "{k}" and minus_config != minus_config', fmt="{:+.2f}",
                                              label="SITL measured", doc=doc) + "}"
            t["chg_dd"] = "\\mbox{" + c("cs7_chg_dd", L7, "difference", 'config == "pqsig_real" and minus_config == "hybrid_published"', fmt="{:+.2f}",
                                         label="SITL measured", doc=doc) + "}"
        R7 = "sitl/results_r7/rerun_check.csv"
        if (ROOT / R7).exists():
            t["rerun_max"] = c("cs7_rerun_max", R7, "difference", 'reference == "round 6"', "max", "{:.2f}", label="SITL measured", doc=doc)
            t["rerun_min"] = c("cs7_rerun_min", R7, "difference", 'reference == "round 6"', "min", "{:.2f}", label="SITL measured", doc=doc)

    rows = []
    for k, name in CFGS:
        hs = t.get(f"{k}_hs", "--")
        lat = t.get(f"{k}_lat", "ref.")
        if k == "signing":
            name += "$^{a}$"
        rows.append(f"{name} & {hs} & {lat} & {t[k + '_av']} [{t[k + '_av_lo']}, {t[k + '_av_hi']}] & {t[k + '_mpm']} \\\\")
    if r7:
        for k, name in (("pqsig_falcon", "Falcon-512 per command$^{b}$"), ("pqsig_falcon_counter", "Falcon-512 per command, counter$^{b}$")):
            rows.append(f"{name} & -- & {t[k + '_lat']} & {t[k + '_av']} [{t[k + '_av_lo']}, {t[k + '_av_hi']}] & {t[k + '_mpm']} \\\\")
    table = r"""\begin{table*}[t]
\centering
\caption{ArduPilot SITL behind the gateway emulation and an emulated SiK class radio, """ + t["n_miss"] + r""" paired missions per configuration}
\label{tab:sitl}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{lrrrr}
\toprule
Configuration & Handshake (s) & Added round trip (ms) & Share acknowledged within 0.5~s [95\% CI] & Missed per mission \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}

\smallskip\footnotesize Handshake: median from F1 until both sides hold the key (vehicle accepting F3 for design K, ground accepting F4 otherwise), emulated link and executed cryptography with RTL derived vehicle delays. Added round trip: median round trip to the flight stack's acknowledgement against no authentication (SITL measured). Acknowledged share and missed commands (not acknowledged within 0.5~s) include one outage per mission. $^{a}$ signing inside ArduPilot and the ground station at host speed, without RTL derived delays.""" + (r" $^{b}$ flown after the other configurations, on the same seeds." if r7 else "") + r"""
\end{table*}
"""
    s = {}
    s["dos_k"], s["dos_h"], s["flight_s"] = t["dos_k"], t["dos_h"], t["flight_s"]
    s["pqsig_def"] = ("as in earlier per command designs it carries no counter, so it does not resist replay and is weaker than the sessions"
                      + ("; a second variant adds a 6~B counter under the published rule, so it resists replay." if "pqsig_counter" in keys else "."))
    s["rules"] = ("The \\emph{strict} rule accepts only the next counter; when the ground station's link layer gives up a frame, or when the vehicle sees a later counter and the next one does not arrive, the two sides resynchronise, either by a full new handshake"
                  + (" or, in the second variant, by one authenticated message each way under the existing session key." if "hybrid_strict_inband" in keys else "."))
    s["abstract"] = ("a session keeps the per command cost of the shipped tag and misses almost no more commands than no authentication, while a signature per command misses the 0.5~s deadline for most commands ("
                     + t["pqsig_real_av"] + " acknowledged in time; " + t["pq_dl_1.0"] + " within 1~s). A strict counter rule misses " + t["m_hybrid_strict_hybrid_published"]
                     + " more commands per mission after outages, and still " + t.get("m_hybrid_strict_inband_hybrid_published", "more") + " when it resynchronises inside the session; a replay cache misses none more than the published rule.")
    s["method"] = ("The configurations fly " + t["n_miss"] + " missions each on the same seeds, so they see the same outages; mission lengths differ slightly, so the number of commands per configuration ranges from "
                   + t["cmd_min"] + " to " + t["cmd_max"] + ". We therefore compare configurations by the commands missed per mission, paired by mission, with bootstrap intervals over missions"
                   + ". The host was slower than the applied delay for " + t["hx_tag"] + " of " + t["hx_tag_n"]
                   + " vehicle side tags (at most " + t["hx_tag_max"] + " in one configuration); these are counted, not corrected.")
    fig = ("\\begin{figure}[t]\n\\centering\n\\includegraphics[width=\\columnwidth]{fig_sitl.pdf}\n"
           "\\caption{Paired differences between configurations of the commands missed per mission (not acknowledged within 0.5~s, outages included), mean over missions with 95\\% bootstrap interval (SITL measured). Negative values mean fewer missed commands than the reference. Filled circles: the " + t["n_miss"] + " missions of Table~\\ref{tab:sitl}" + ("; open squares: " + t["n100"] + " missions; open triangles: " + t["n20b"] + " missions under burst loss" if "n100" in t else "") + ".}\n"
           "\\label{fig:sitl}\n\\end{figure}\n")
    sec = (table + fig + "Table~\\ref{tab:sitl} gives each configuration. Once a session exists, its per message cost is that of the shipped tag: the hybrid session adds "
           + t["hybrid_published_lat"] + "~ms to the median command round trip, the classical session " + t["classical_lat"] + "~ms and signing as shipped, which runs inside the flight stack without gateways, "
           + t["signing_lat"] + "~ms. These milliseconds are mostly airtime of the 13~B signing field (" + t["air13"] + "~ms per direction; applied tag delays " + t["tagd_lo"] + " to " + t["tagd_hi"] + "~ms). The hybrid handshake takes "
           + t["hybrid_published_hs"] + "~s over the emulated radio against " + t["classical_hs"] + "~s for the classical session, a cost paid once per session"
           + (", and design K completes in " + t["kem_auth_hs"] + "~s" if "kem_auth" in keys else "") + ". Signing as shipped missed " + t["sign_nack"]
           + " commands that arrived after a newer frame and failed the shipped timestamp rule.\n\n")
    sec += ("An ML-DSA-44 signature on every command adds " + t["pqsig_real_lat"] + "~ms to each round trip, mostly airtime of the 2.4~kB signature, since the applied verification delay is "
            + t["pq_delay"] + "~ms; this puts the median round trip next to the deadline: " + t["pqsig_real_av"] + " of its commands are acknowledged within 0.5~s and " + t["pq_dl_1.0"] + " within 1~s.\n\n")
    sec += ("Fig.~\\ref{fig:sitl} compares configurations by the commands missed per mission. Most session configurations differ in at most three of the " + t["n_miss"]
            + " missions: the hybrid session misses " + t["m_hybrid_published_none"] + " commands per mission against no authentication and " + t["m_hybrid_published_classical"] + " against the classical session, "
            "a small cost from re-handshakes after long outages; design K and the classical session miss the same commands (" + t["m_kem_auth_classical"] + "). "
            "Link layer retransmission delivers some frames after newer ones (reordering depth up to " + t["reorder_depth"] + "), and the published rule rejected " + t["pub_late"]
            + " of them as late; the replay cache accepted them, but they had already missed the deadline, so the cache misses exactly as many commands as the published rule ("
            + t["m_hybrid_cache_hybrid_published"] + ", " + t["m_hybrid_cache_hybrid_published_n"] + " missions differ).\n\n")
    sec += ("The strict rule is the one that costs commands. Resynchronising by a full new handshake, it misses " + t["m_hybrid_strict_hybrid_published"] + " commands per mission against the published rule ("
            + t["m_hybrid_strict_hybrid_published_lo"] + " to " + t["m_hybrid_strict_hybrid_published_hi"] + "), mainly through resynchronisation, not reordering: "
            + t["strict_nosession"] + " commands were lost while no session existed during " + t["resync"] + " resynchronisations, " + t["resync_gu"]
            + " of them triggered when the link layer gave up a frame during an outage, against " + t["strict_ahead"] + " rejected as ahead of the expected counter; "
            + t["rs_strict"] + " of its missions restarted the session, against " + t["rs_pub"] + " under the published rule.")
    if "hybrid_strict_inband" in keys:
        sec += (" Resynchronising inside the session removes the handshake but not the cost: across " + t["resync_in"]
                + " resynchronisations it still misses " + t["m_hybrid_strict_inband_hybrid_published"] + " commands per mission against the published rule ("
                + t["m_hybrid_strict_inband_hybrid_published_lo"] + " to " + t["m_hybrid_strict_inband_hybrid_published_hi"] + "), " + t["m_hybrid_strict_inband_hybrid_strict"]
                + " against the strict rule with a new handshake, because every command sent while the counter is out of step is rejected.")
    if "pqsig_counter" in keys:
        sec += (" Adding a counter to the signature per command does not change its availability (" + t["m_pqsig_counter_pqsig_real"] + " commands per mission, "
                + t["m_pqsig_counter_pqsig_real_lo"] + " to " + t["m_pqsig_counter_pqsig_real_hi"] + ").")
    s["section"] = sec
    s["disc"] = ("A signature per command, as measured here with ML-DSA-44, fits only commands that can wait about a second. "
                 "The replay rule should be a replay cache that checks and records atomically: a strict rule costs commands after outages even when it resynchronises without a new handshake.")
    s["conclusion"] = ("Executed under one set of conditions, a hybrid post quantum session for drone commands costs " + "{hyb_lo} to {hyb_hi}"
                       + " times the vehicle side computation of a classical session on these cores and many times its handshake bytes, yet keeps the per command cost of the shipped tag; "
                       "a KEM authenticated session with pinned keys is the cheapest post quantum option but rests on ML-KEM alone, and a signature per command misses a 0.5~s deadline for most commands. "
                       "The replay rule matters as much as the algorithms: a strict rule loses commands after outages, with or without a new handshake, while a replay cache loses none against the published rule and is safe only if it checks and records each counter in one step.")
    if r7:
        big = "large100_hybrid_strict_hybrid_published" in t
        st = "large100" if big else "burst20"
        s["pqsig_def"] = ("as in earlier per command designs it carries no counter, so it does not resist replay and is weaker than the sessions; "
                          "a second variant of each adds a 6~B counter under the published rule, so it resists replay.")
        s["abstract"] = ("a session keeps the per command cost of the shipped tag and misses almost no more commands than no authentication. "
                         "With a signature per command, " + t["pqsig_real_av"] + " of commands meet a 0.5~s deadline with ML-DSA-44 and " + t["pqsig_falcon_av"]
                         + " with Falcon-512, whose signing costs @FALRG@ times as many cycles with emulated floating point. "
                         + ("Over " + t["n100"] + " missions per configuration, a" if big else "A") + " strict counter rule misses "
                         + t[f"{st}_hybrid_strict_hybrid_published"] + " commands per mission more than the published rule after outages, and still "
                         + t[f"{st}_hybrid_strict_inband_hybrid_published"] + " when it resynchronises inside the session; a replay cache misses almost none more ("
                         + t[f"{st}_hybrid_cache_hybrid_published"] + ").")
        s["method"] += (" Two further sets use the same seeds: under a two state burst loss model with the same mean frame loss and a mean burst of "
                        + t["burst_frames"] + " frames (an assumption without a measured radio source), " + t["n20b"] + " missions each"
                        + ((", and under independent loss " + t["n100"] + " missions each, for nine configurations") if big else "")
                        + "; all ran in two lanes at once, and the Falcon-512 configurations were added after the first runs.")
        sec = s["section"]
        sec += ("\n\nA Falcon-512 signature per command, with " + t["fal_delay"] + "~ms of verification at the applied clock, adds " + t["pqsig_falcon_lat"]
                + "~ms to the round trip, mostly the airtime of its " + t["fal_sig_b"] + "~B signature, and " + t["pqsig_falcon_av"] + " [" + t["pqsig_falcon_av_lo"] + ", " + t["pqsig_falcon_av_hi"]
                + "] of its commands are acknowledged within 0.5~s, against " + t["pqsig_real_av"] + " for ML-DSA-44. Its missed commands per mission differ by " + t["falcon20_pqsig_falcon_pqsig_real"]
                + " from ML-DSA-44 (" + t["falcon20_pqsig_falcon_pqsig_real_lo"] + " to " + t["falcon20_pqsig_falcon_pqsig_real_hi"] + ") and by "
                + t["falcon20_pqsig_falcon_hybrid_published"] + " from the hybrid session, and its counter changes nothing (" + t["falcon20_pqsig_falcon_counter_pqsig_falcon"]
                + "). The price is on the ground side: signing took " + t["fal_sign_host"] + "~ms on the host, and on the cores many times ML-DSA-44 signing (Section~\\ref{sec:rtl}).")
        sec += ("\n\nThe replay rule results hold under burst loss and over more missions (Fig.~\\ref{fig:sitl}). Under burst loss the strict rule with a new handshake misses "
                + t["burst20_hybrid_strict_hybrid_published"] + " commands per mission against the published rule (" + t["burst20_hybrid_strict_hybrid_published_lo"] + " to "
                + t["burst20_hybrid_strict_hybrid_published_hi"] + "), in session " + t["burst20_hybrid_strict_inband_hybrid_published"] + ", and the cache "
                + t["burst20_hybrid_cache_hybrid_published"] + ". Bursts did not hurt the per command signatures more than the sessions: from independent to burst loss the missed commands per mission of ML-DSA-44 per command changed by "
                + t.get("chg_pqsig_real", "") + " and those of the hybrid session by " + t.get("chg_hybrid_published", "")
                + ", probably because with the same mean loss bursts hit fewer of the many frames that carry one signed command; we did not check this frame by frame.")
        if big:
            sec += (" Over " + t["n100"] + " missions under independent loss, the strict rule misses " + t["large100_hybrid_strict_hybrid_published"] + " ("
                    + t["large100_hybrid_strict_hybrid_published_lo"] + " to " + t["large100_hybrid_strict_hybrid_published_hi"] + ") and in session "
                    + t["large100_hybrid_strict_inband_hybrid_published"] + " (" + t["large100_hybrid_strict_inband_hybrid_published_lo"] + " to "
                    + t["large100_hybrid_strict_inband_hybrid_published_hi"] + ") against the published rule, against " + t["m_hybrid_strict_hybrid_published"] + " and "
                    + t["m_hybrid_strict_inband_hybrid_published"] + " over the first " + t["n_miss"] + "; the cache misses " + t["large100_hybrid_cache_hybrid_published"] + " more (" + t["large100_hybrid_cache_hybrid_published_lo"] + " to "
                    + t["large100_hybrid_cache_hybrid_published_hi"] + "), so it is not exactly even with the published rule. Reruns of the first " + t["n_miss"] + " seeds moved configuration means by " + t["rerun_min"] + " to " + t["rerun_max"]
                    + ", as the flight stack runs in real time.")
        s["section"] = sec
        s["thr"] = ("(iv) The radio is an emulation with one scripted outage per mission; burst loss is covered only by one two state model with one assumed burst length, not by a radio trace, "
                    "and the strict rule results rest on outage triggered events. (v) " + ("Twenty missions per configuration for most results and " + t["n100"] + " for nine configurations" if big else "Twenty missions per configuration")
                    + ", a bootstrap over missions that may under cover, and no correction for the several paired comparisons.")
        s["disc"] = ("An ML-DSA-44 signature per command fits only commands that can wait about a second; a Falcon-512 signature (@FALSIG@~B against @MLDSASIG@~B per signed command here) "
                     "keeps most commands on time at a small vehicle cost, if the ground side can afford signing at @FALRG@ times the cycles of ML-DSA-44 with emulated floating point, "
                     "or has a floating point unit, which our cores lack.")
        s["conclusion"] = ("Executed under one set of conditions, a hybrid post quantum session for drone commands costs " + "{hyb_lo} to {hyb_hi}"
                           + " times the vehicle side computation of a classical session on these cores and many times its handshake bytes, yet keeps the per command cost of the shipped tag; "
                           "a KEM authenticated session with pinned keys is the cheapest post quantum option but rests on ML-KEM alone. An ML-DSA-44 signature per command misses a 0.5~s deadline for most commands, "
                           "while a Falcon-512 signature keeps most commands on time at @FALRG@ times the signing cost. "
                           "The replay rule matters as much as the algorithms: a strict rule loses commands after outages, with or without a new handshake, over more missions and under burst loss, "
                           "while a replay cache loses almost none against the published rule and is safe only if it checks and records each counter in one step.")
    return t, s


def formal_text(c, doc):
    """Section on the ProVerif results, read from formal/results/proverif_results.csv. Statements about models that
    exist only after the round 6 revision (reachability checks in the hybrid models, a broken signature component)
    are written only when their rows are present."""
    import pandas as pd
    pv = pd.read_csv(ROOT / PV)
    models = set(pv.model)

    def k(cid, q, agg="count", col="result", fmt="{:.0f}", label="modelled"):
        return c(cid, PV, col, q, agg, fmt, label=label, doc=doc)
    hyb_reach = bool(((pv.model == "session_b_fixed") & pv.property_id.str.startswith("R")).any())
    sig = sorted(m for m in models if m.startswith("session_b_fixed") and "sig" in m)
    out = ("ProVerif checked " + k("cf_pv_q", "") + " queries in " + c("cf_pv_m", PV, "model", "", "nunique", "{:.0f}", label="modelled", doc=doc)
           + " model files: " + k("cf_pv_p", 'result == "proved"') + " proved, " + k("cf_pv_cx", 'result == "counterexample"') + " counterexamples, "
           + k("cf_pv_cnp", 'result == "cannot be proved"') + " that the tool could not prove and " + k("cf_pv_to", 'result.str.startswith("cannot be proved (timeout")')
           + " that reached the time limit. Of the counterexamples, " + k("cf_pv_r0", 'property_id.str.startswith("R") and result == "counterexample"')
           + " are reachability checks that must fail: they show that a command or a session key can be accepted, so the agreement results are not vacuous"
           + ("" if hyb_reach else " (the hybrid session models have no such check)")
           + ". The others come from designs before their fixes, models not discussed here, deliberate controls and the results below. ")
    out += ("With mutual signing the hybrid session keys stay secret and each side authenticates the other; the keys stay secret when either the classical or the KEM component is broken, "
            "and after a later theft of the long term keys.")
    if sig:
        def res(m, pid):
            r = pv[(pv.model == m) & (pv.property_id == pid)]
            return r.result.iloc[0] if len(r) else None
        m0 = "session_b_fixed_sig_broken" if "session_b_fixed_sig_broken" in models else sig[0]
        auth = [pid for pid in ("A1", "A2") if res(m0, pid) == "counterexample"]
        sm = res(m0, "SM") == "proved"
        out += (" With ML-DSA-44 broken (both signing keys known to the attacker), " + ("authentication fails and an active attacker learns the key a side accepts" if auth else "authentication still holds")
                + ("; only a session that both sides accepted with the same key stays secret, which the X25519 and ML-KEM exchange still gives" if sm else "")
                + ". The hybrid session's authentication therefore rests on ML-DSA-44 alone.")
    out += ("\n\nDesign K keeps its keys secret when the classical component is broken and after a later theft of the static keys, and the vehicle authenticates the ground station. "
            "With ML-KEM broken, however, its keys are not secret: the attacker sends its own first flight with stolen static keys, and the X25519 share does not save the session against an active attacker; "
            "with its static keys known, design K fares like the hybrid session with ML-DSA-44 broken. Authentication of the vehicle by the ground station is proved only in a model in which static and ephemeral KEM keys have distinct types; ")
    a2 = pv[(pv.model == "session_kemauth_a2_retry") & (pv.property_id == "A2")]
    if len(a2) and a2.result.iloc[0].startswith("cannot"):
        out += ("the general model reached a time limit of " + c("cf_pv_a2_t", PV, "run_time_s_host_measured", 'model == "session_kemauth_a2_retry" and property_id == "A2"',
                                                                    "value", "{:.0f}", 1 / 3600, label="host measured", doc=doc) + "~h without finding an attack or a proof.")
    else:
        out += "the general model " + ("proves it as well." if len(a2) and a2.result.iloc[0] == "proved" else "gives " + a2.result.iloc[0] + ".")
    out += ("\n\nFor out of order delivery, a replay cache proves injective agreement on commands when the vehicle checks and records each pair of session and counter in one step and never forgets an entry, "
            "a condition stated in the model as a restriction, not derived. When concurrent branches read a table before either records, the model gives a counterexample, and a table read in sequence could not be proved; "
            "an implementation must therefore check and record atomically. A bounded window was proved only on the command layer for a window of two counters, and the published timestamp rule could not be proved.")
    return out


def build(claim):
    """Return [(path, text)] for the two versions of the conference paper."""
    write_derived()
    out = []
    for doc, anon in ((DOC, False), (DOC_ANON, True)):
        n = numbers(claim, doc)
        _, s = sitl_numbers(claim, doc)
        s["formal"] = formal_text(claim, doc)
        out.append((doc, text(n, s, anon)))
    (ROOT / "docs/conference").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/conference/references.bib").write_text(bib(), encoding="utf-8")
    return out
