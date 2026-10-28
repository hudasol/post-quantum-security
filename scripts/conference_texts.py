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
DESIGN_NAMES = {"classical": "Classical", "pq_only": "PQ only", "hybrid_f1": "Hybrid, F1", "kem_auth": "KEM authenticated (K)"}


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
    """BibTeX entries from data/conference/references.csv."""
    out = []
    for r in csv.DictReader(open(ROOT / "data/conference/references.csv", encoding="utf-8")):
        if r["key"] in ORG_KEYS:
            r["author"] = "{" + r["author"] + "}"  # corporate author, kept whole by BibTeX
        out.append("@misc{%s,\n  author = {%s},\n  title = {{%s}},\n  howpublished = {%s, \\url{%s}},\n  year = {%s}\n}\n"
                   % (r["key"], r["author"], r["title"].replace("&", "\\&"), r["venue"].replace("&", "\\&").replace("_", "\\_"), r["url"], r["year"]))
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
    n["pv_q"] = c("cf_pv_q", PV, "result", aggregate="count", label="modelled", doc=doc)
    n["pv_m"] = c("cf_pv_m", PV, "model", aggregate="nunique", label="modelled", doc=doc)
    n["pv_p"] = c("cf_pv_p", PV, "result", 'result == "proved"', "count", label="modelled", doc=doc)
    n["pv_cx"] = c("cf_pv_cx", PV, "result", 'result == "counterexample"', "count", label="modelled", doc=doc)
    n["pv_cnp"] = c("cf_pv_cnp", PV, "result", 'result == "cannot be proved"', "count", label="modelled", doc=doc)
    n["pv_r0"] = c("cf_pv_r0", PV, "result", 'property_id == "R0" and result == "counterexample"', "count", label="modelled", doc=doc)
    n["pv_a2_t"] = c("cf_pv_a2_t", PV, "run_time_s_host_measured", 'model == "session_kemauth_a2" and property_id == "A2"', fmt="{:.0f}",
                     label="host measured", doc=doc)
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
    return r"\author{\IEEEauthorblockN{Huda Mueen}\IEEEauthorblockA{Independent researcher, United Arab Emirates\\hudamueen2407@gmail.com}}"


def artifact(anon):
    if anon:
        return "The code, data, logs and scripts are in a public repository whose link is withheld for review."
    return f"The code, data, logs and scripts are public at \\url{{{REPO}}}."


def text(n, s, anon):
    """The paper. n: RTL, formal and set up numbers; s: software in the loop and mission numbers."""
    meta = "" if anon else "\\pdfinfo{/Author (Huda Mueen)}\n"
    return PREAMBLE + meta + r"""
\title{Post Quantum Session Authentication for Drone Command Links: Executed Baselines, Flight Stack in the Loop and Replay Rules}
""" + authors(anon) + r"""
\maketitle

\begin{abstract}
Flight controllers fielded today may still be in service when an attacker can forge classical signatures and break classical key exchange. We execute six command channel designs under one set of conditions: MAVLink 2 signing as shipped, a classical session (X25519, Ed25519), a post quantum only session (ML-KEM-768, ML-DSA-44), a hybrid session of both, a session authenticated only by pinned static ML-KEM-768 keys, and an ML-DSA-44 signature on every command. On two open RISC-V core designs in cycle accurate RTL simulation, the hybrid session costs """ + n["cv32e40p_r_hybrid_f1_classical_vehicle"] + r""" to """ + n["ibex_r_hybrid_f1_classical_vehicle"] + r""" times the vehicle side computation of the classical session, the KEM authenticated session """ + n["cv32e40p_r_kem_auth_classical_vehicle"] + r""" to """ + n["ibex_r_kem_auth_classical_vehicle"] + r""" times, and a signature per command """ + n["cv32e40p_pqc_over_tag_vehicle"] + r""" to """ + n["ibex_pqc_over_tag_vehicle"] + r""" times a per message tag. """ + s["abstract"] + r""" ProVerif proves injective agreement on commands for that cache only when the vehicle checks and records each counter in one step, and finds that the KEM authenticated session loses key secrecy once ML-KEM alone is broken. """ + artifact(anon) + r"""
\end{abstract}

\section{Introduction}
A small multirotor runs its flight stack on a microcontroller and receives commands over a telemetry radio of tens of kilobits per second. MAVLink 2, the common protocol, offers a per message tag with a pre shared key \cite{mavsign}; without it, commands can be injected from the radio side \cite{kwon18,koubaa19}, and key establishment and endpoint authentication are left to the operator. Vehicles and their firmware stay in service for years, so a key exchange or signature that a future quantum computer breaks would let an attacker inject commands in real time during that service life. The replacements are standardised: ML-KEM for key establishment \cite{fips203} and ML-DSA for signatures \cite{fips204}.

Hyoung et al.\ measure post quantum TLS handshakes over an emulated drone radio and argue that, after the handshake, commands should carry only a symmetric tag \cite{hyoung26}; the per command cost there is derived, not measured, and acceptance of reordered or lost commands is not considered. Primitive benchmarks \cite{pqm4}, post quantum TLS on embedded systems \cite{burstinghaus20,gonzalez22} and KEM based authentication \cite{kemtls20,kemtlspdk21,pqwg21,pqnoise22} answer other parts. What an engineer cannot yet read from published evidence is how complete command channel designs, including a signature free KEM authenticated one, compare on the same core, the same link and the same flight stack, and what the replay rule does to availability.

This paper contributes:
(1) executed baselines of six command channel designs on two open RISC-V core designs in cycle accurate RTL simulation, with correctness checks, intervals over """ + n["runs"] + r""" runs, stack and code size, under one compiler and pinned libraries (Section~\ref{sec:rtl});
(2) ArduPilot in the loop with gateways that execute the real handshakes, tags and replay rules on paired seeds, with the sensitivity of each result to the command deadline (Section~\ref{sec:sitl});
(3) ProVerif models of the hybrid and the KEM authenticated sessions and of replay rules that accept out of order delivery, with the bounds of each model (Section~\ref{sec:formal});
(4) a pre registered, script checked method in which every number in this paper is read from a committed result file.

\section{Threat model and designs}
\label{sec:design}
\emph{Threat model.} The attacker controls the radio: it reads, drops, delays, reorders and injects frames and replays old ones, and it may hold a quantum computer during the service life of the vehicle. Endpoints, their long term keys and the flight stack are trusted; side channels, jamming beyond the modelled loss and outages, and the confidentiality of commands are out of scope. The goals are mutual authentication of the session endpoints, secrecy of the session key that keys the tags, and injective agreement on commands: every accepted command was sent by the ground station in that session and is accepted at most once.

\emph{Session designs.} All sessions end with the MAVLink 2 signing field of 13~B per message, keyed by the session key \cite{mavsign}. \emph{Classical}: X25519 key exchange, Ed25519 signatures by both sides over the transcript and both identities, key confirmation tags. \emph{Post quantum only}: ML-KEM-768 and ML-DSA-44 in the same roles. \emph{Hybrid} (proposed): X25519 and ML-KEM-768 together, the session key derived from both secrets and a transcript hash, ML-DSA-44 signatures by both sides; a design in which only the ground station signs leaves the vehicle unauthenticated in our model, and the vehicle signature (change F1) closes it. \emph{KEM authenticated} (design K): each side holds the other's static ML-KEM-768 key; the ground station sends an X25519 share, an ephemeral ML-KEM-768 key and an encapsulation to the vehicle's static key, the vehicle answers with its share, a ciphertext to the ephemeral key, an encapsulation to the ground station's static key and a confirmation tag, and the ground station confirms; there are no signatures, as in post quantum WireGuard and KEMTLS with pre distributed keys \cite{pqwg21,kemtlspdk21}. Table~\ref{tab:flights} gives the bytes of each flight.

\emph{Baselines without a session.} \emph{Signing as shipped}: a provisioned key, no handshake. \emph{Signature per command}: an ML-DSA-44 signature on every command, verified by the vehicle; like the corresponding baseline of earlier mission models it carries no counter, so it does not resist replay and is weaker than the sessions.

\emph{Replay rules.} The vehicle accepts a command under one of three rules: \emph{published} (counter greater than the last accepted, gaps allowed) \cite{mavsign}; \emph{strict} (only the next counter; the ground station starts a new handshake when its link layer gives up a frame, or when the vehicle asks because a later counter arrived and the next did not); and \emph{replay cache} (any counter not yet accepted within a window of """ + n["win"] + r""" counters).

\begin{table}[t]
\centering
\caption{Bytes per handshake flight as built by the executed protocols}
\label{tab:flights}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{lrrrrr}
\toprule
Design & F1 & F2 & F3 & F4 & Total \\
\midrule
""" + flights_rows(n) + r"""
\bottomrule
\end{tabular}

\smallskip\footnotesize F1 and F3 ground to vehicle, F2 and F4 vehicle to ground; MAVLink framing and link fragmentation not included.
\end{table}

\section{Method}
\label{sec:method}
\emph{RTL simulation.} Ibex in its small configuration \cite{ibex} and CV32E40P \cite{cv32e40p}, both RV32IMC without caches or wait states, are simulated cycle accurately with Verilator. One firmware image per design runs the vehicle and the ground side, each step timed with the cycle counter, """ + n["runs"] + r""" runs per image with a fixed seed block; every run checks that both sides derive the same key, that all signatures and tags verify, and known answers for the hash functions. Medians carry 95\% intervals over runs. Libraries are pinned and unmodified: mlkem-native \cite{mlkemnative}, mldsa-native \cite{mldsanative} and Monocypher \cite{monocypher}, all portable C, compiled with one compiler at \texttt{-O3}. Peak stack is measured by stack painting and includes the harness; code size is the text section of each image with unused sections removed, both sides and the harness included.

\emph{Software in the loop.} ArduPilot Copter 4.7.2 \cite{ardupilot} flies a scripted mission of about one minute (take off, two legs, land) with its built in vehicle model; the ground station sends one acknowledged command per second. A relay emulates a SiK class radio of """ + n["sik_kbps"] + r"""~kbit/s with independent frame loss of """ + n["loss"] + r""", link layer retransmission that can deliver frames out of order, and one outage per mission starting """ + n["out_a"] + r"""--""" + n["out_b"] + r"""~s after arming with an exponential duration of mean """ + n["out_mean"] + r"""~s; an outage longer than """ + n["sess_to"] + r"""~s tears the session down. A gateway pair in front of the ground station and the flight stack executes the handshake, the tags and the replay rule with the same algorithms (Python cryptography and host builds of the same libraries). Vehicle side operations are released after a delay equal to their Ibex cycles at """ + n["clock"] + r"""~MHz, fixed from the first runs before the flights; ground side compute runs at host speed. """ + s["method"] + r"""

\emph{Formal models.} ProVerif \cite{proverif} checks secrecy, agreement and reachability under a Dolev Yao attacker with abstract primitives and unbounded sessions. Session models carry one command, a rekey and a further command per session; replay cache models carry three commands per key; the bounded window is modelled on the command layer for a window of two counters. Rekey grace periods, counter wrap and timestamps are not modelled. Breaking a component is modelled by giving its secrets to the attacker.

\emph{Discipline.} """ + n["q_n"] + r""" predictions with refutation clauses were hashed before the runs and scored by script under the less favourable reading of any ambiguous clause: """ + n["q_hit"] + r""" hit, """ + n["q_between"] + r""" between and """ + n["q_miss"] + r""" missed. The thresholds were broad, so the hits say less than the misses. Every number in this paper is registered with its file, column and query and checked by a script in continuous integration.

\section{Executed baselines on core designs}
\label{sec:rtl}
""" + rtl_table(n) + r"""
\begin{figure}[t]
\centering
\includegraphics[width=\columnwidth]{fig_rtl.pdf}
\caption{Vehicle side cycles of one session start on CV32E40P by primitive (RTL simulated, medians). The whisker spans the fastest and slowest ML-DSA-44 signing observed; the dot is the measured median of the whole session.}
\label{fig:rtl}
\end{figure}
Table~\ref{tab:rtl} gives the cost of one session start and of one command. The hybrid session costs """ + n["cv32e40p_r_hybrid_f1_classical_vehicle"] + r"""$\times$ [""" + n["cv32e40p_r_hybrid_f1_classical_vehicle_lo"] + r""", """ + n["cv32e40p_r_hybrid_f1_classical_vehicle_hi"] + r"""] the classical vehicle side on CV32E40P and """ + n["ibex_r_hybrid_f1_classical_vehicle"] + r"""$\times$ [""" + n["ibex_r_hybrid_f1_classical_vehicle_lo"] + r""", """ + n["ibex_r_hybrid_f1_classical_vehicle_hi"] + r"""] on Ibex; on the ground side, which signs first, """ + n["cv32e40p_r_hybrid_f1_classical_ground"] + r"""$\times$ and """ + n["ibex_r_hybrid_f1_classical_ground"] + r"""$\times$. Over the post quantum only session it costs """ + n["cv32e40p_r_hybrid_f1_pq_only_vehicle"] + r"""$\times$ [""" + n["cv32e40p_r_hybrid_f1_pq_only_vehicle_lo"] + r""", """ + n["cv32e40p_r_hybrid_f1_pq_only_vehicle_hi"] + r"""] on the vehicle side and """ + n["cv32e40p_r_hybrid_f1_pq_only_ground"] + r"""$\times$ on the ground side. The two designs differ by two X25519 multiplications, a fixed cost, while ML-DSA-44 signing repeats with rejection and took """ + n["sign_min"] + r""" to """ + n["sign_max"] + r"""~M cycles per signature (Fig.~\ref{fig:rtl}); the spread of a signing design comes from there. With Monocypher, one X25519 multiplication (""" + n["cv_x25519_shared"] + r"""~M cycles on CV32E40P) costs more than an ML-KEM-768 encapsulation (""" + n["cv_mlkem768_encaps"] + r"""~M), and an Ed25519 verification """ + n["cv_ed25519_verify"] + r"""~M; this is a property of one portable C library designed for size, and a faster classical library would raise every ratio over the classical session.

Design K avoids both ML-DSA-44 operations: its vehicle side costs """ + n["cv32e40p_r_kem_auth_classical_vehicle"] + r"""$\times$ the classical session and """ + n["cv32e40p_r_kem_auth_hybrid_f1_vehicle"] + r"""$\times$ [""" + n["cv32e40p_r_kem_auth_hybrid_f1_vehicle_lo"] + r""", """ + n["cv32e40p_r_kem_auth_hybrid_f1_vehicle_hi"] + r"""] the hybrid one, it needs """ + n["stack_kem_auth"] + r"""~kB of stack against """ + n["stack_hybrid_f1"] + r"""~kB for the hybrid (""" + n["stack_classical"] + r"""~kB classical), and it carries """ + n["bytes_kem_auth"] + r"""~B in three flights against """ + n["bytes_hybrid_f1"] + r"""~B, """ + n["bytes_hyb_over_cls"] + r"""$\times$ the classical handshake. Code grows from """ + n["code_classical"] + r"""~kB (classical) to """ + n["code_hybrid_f1"] + r"""~kB (hybrid) and """ + n["code_kem_auth"] + r"""~kB (design K). After the handshake a command costs a tag check of """ + n["tag_v"] + r""" cycles on a COMMAND\_LONG; verifying an ML-DSA-44 signature on the same frame instead costs """ + n["cv32e40p_pqc_over_tag_vehicle"] + r"""$\times$ as much, and signing it on the ground side about twice that. At """ + n["clock"] + r"""~MHz the vehicle side of the hybrid session start would take about """ + n["t168_hyb"] + r"""~ms on CV32E40P (estimated), against """ + n["t168_cls"] + r"""~ms for the classical session. Ibex needs """ + n["core_ratio_hyb"] + r"""$\times$ the cycles of CV32E40P for the same hybrid handshake, so a cycle count for one core of an instruction set does not transfer to another.

\section{Flight stack in the loop and availability}
\label{sec:sitl}
""" + s["section"] + r"""

\section{Formal results}
\label{sec:formal}
ProVerif checked """ + n["pv_q"] + r""" queries in """ + n["pv_m"] + r""" model files: """ + n["pv_p"] + r""" proved, """ + n["pv_cx"] + r""" counterexamples and """ + n["pv_cnp"] + r""" that the tool could not prove. Of the counterexamples, """ + n["pv_r0"] + r""" are reachability checks that must fail (they show that the vehicle can accept a command, so agreement is not proved vacuously); the others are found in the designs before the fixes, in deliberate controls with a broken component or a missing check, and in the two results below that matter for the designs. With F1 the hybrid session keys stay secret and each side authenticates the other; the keys stay secret when either the classical or the KEM component is broken, and after a later theft of the long term keys.

Design K keeps its keys secret when the classical component is broken and after a later theft of the static keys, and the ground station authenticates the vehicle. With ML-KEM broken, however, its keys are not secret: the attacker sends its own first flight with stolen static keys, and the X25519 share does not save the session against an active attacker, whereas the hybrid session still has its signatures. Authentication of the ground station by the vehicle is proved only in a model in which static and ephemeral KEM keys have distinct types; the general model reached the time limit of """ + n["pv_a2_t"] + r"""~s without a result.

""" + s["formal"] + r"""

\section{Discussion and limitations}
For streamed commands the results support a session: its post quantum cost is paid once, and the per command cost stays that of the shipped tag. Where both identities can be pinned, design K halves the vehicle side cost and the stack of the hybrid session, at the price of resting authentication on ML-KEM alone; the hybrid session keeps the classical component as a guard against a flaw in ML-KEM. A signature per command fits rare, high value commands with a deadline of about a second, not a stream. The replay rule should be a replay cache that checks and records atomically.

\emph{Threats to validity.} (i) Cycles come from two open core designs with single cycle memories; Cortex-M flight controllers have flash wait states, caches and other multipliers, and stack optimised signing \cite{greconici21} or RISC-V extensions \cite{alkim20,fritzmann20} would change the figures. (ii) One classical library was measured, and it favours the post quantum designs. (iii) In the loop, vehicle compute is a delay at an assumed clock, applied per event without a busy processor, so frames arriving during a verification are not queued behind it; the host was slower than the delay for a small share of tags. (iv) The radio is an emulation with independent frame loss and one scripted outage per mission; real loss is bursty. (v) Twenty missions per configuration, a bootstrap over missions that may under cover, and no correction for the several paired comparisons. (vi) Prior work figures are not comparable to ours because platforms and links differ; Table~\ref{tab:rw} compares methods, not figures. (vii) All reviews of this study so far were internal. The next step is to repeat the executed baselines on Cortex-M4 and Cortex-M33 boards and to fly design K over a real telemetry radio.

\section{Related work}
Primitives are benchmarked on Cortex-M4 with pqm4 \cite{pqm4}, with stack optimised Dilithium \cite{greconici21} and with RISC-V extensions \cite{alkim20,fritzmann20}. Post quantum TLS has been measured on embedded clients \cite{burstinghaus20} and under loss \cite{paquin20,sikeridis20}; KEMTLS \cite{kemtls20,gonzalez22,kemtlspdk21}, post quantum WireGuard and Noise \cite{pqwg21,pqnoise22} authenticate by encapsulation. Firmware signatures have been measured on low power boards and in secure boot \cite{banegas21,kumar20,wagner22,campos20}. For drones, MAVSec encrypts MAVLink \cite{mavsec19} and de Meneses et al.\ verify a post quantum EDHOC variant with estimated costs \cite{meneses26}; for vehicle to vehicle messages, frame loss can decide practicality \cite{twardokus24}. Table~\ref{tab:rw} compares the closest works with this paper.

\begin{table*}[t]
\centering
\caption{Closest prior work and this paper (as recorded from each source)}
\label{tab:rw}
\setlength{\tabcolsep}{3pt}
\footnotesize
\begin{tabular}{llllll}
\toprule
Work & Platform & Link and stack & Per command cost & Availability & Formal check \\
\midrule
\cite{hyoung26} & x86 laptop & emulated UAV radio, TLS 1.3 & derived, not measured & not reported & none reported \\
\cite{burstinghaus20} & Cortex-A53, ESP32, others & Ethernet or Wi-Fi, network excluded & not reported & not reported & none reported \\
\cite{kemtls20,kemtlspdk21} & server or host & emulated network, TLS variants & not reported & not reported & proof on paper \\
\cite{pqwg21} & virtual machines & virtual network, WireGuard & not reported & not reported & Tamarin, with replay \\
\cite{meneses26} & modelled Cortex-M4 & UAV, EDHOC variant, computed delays & not reported & not reported & Tamarin \\
\cite{twardokus24} & V2V chipset & DSRC, simulated and on road & measured & frame loss ratio & proof on paper \\
This paper & two RISC-V cores (RTL), host & emulated SiK radio, ArduPilot in the loop & executed (RTL) & acknowledged share per rule & ProVerif \\
\bottomrule
\end{tabular}
\end{table*}

\section{Conclusion}
Executed under one set of conditions, a hybrid post quantum session for drone commands costs less than twice the computation of a classical session on these cores and many times its handshake bytes, yet leaves the per command cost and """ + s["conclusion"] + r""" A KEM authenticated session with pinned keys is the cheapest post quantum option but rests on ML-KEM alone. The replay rule decides as much as the algorithms: a strict rule loses commands at every outage, and a replay cache that checks and records in one step loses none.

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
            ("Hybrid session, F1", n["ibex_hybrid_f1_vehicle"], n["cv32e40p_hybrid_f1_vehicle"], n["ibex_hybrid_f1_ground"], n["cv32e40p_hybrid_f1_ground"], n["code_hybrid_f1"]),
            ("KEM auth.\\ session (K)", n["ibex_kem_auth_vehicle"], n["cv32e40p_kem_auth_vehicle"], n["ibex_kem_auth_ground"], n["cv32e40p_kem_auth_ground"], n["code_kem_auth"]),
            ("ML-DSA-44 per command$^{b}$", n["ibex_pqc_vehicle"], n["cv32e40p_pqc_vehicle"], n["ibex_pqc_ground"], n["cv32e40p_pqc_ground"], n["code_per_command_mldsa44"])]
    body = "\n".join(f"{a} & {b} & {c} & {d} & {e} & {f} \\\\" for a, b, c, d, e, f in rows)
    return r"""\begin{table}[t]
\centering
\caption{Executed baselines: million cycles per unit (RTL simulated, medians of """ + n["runs"] + r""" runs) and code size on CV32E40P}
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

\smallskip\footnotesize Session rows: one session start. $^{a}$ check (vehicle) and generation (ground) of one tag over a COMMAND\_LONG frame. $^{b}$ verification (vehicle) and signing (ground) of one command.
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
            ("hybrid_published", "Hybrid, published rule"), ("hybrid_strict", "Hybrid, strict rule"),
            ("hybrid_cache", "Hybrid, replay cache"), ("kem_auth", "Design K, published rule"), ("pqsig_real", "ML-DSA-44 per command")]
# paired differences of the share acknowledged within 0.5 s that the paper and Fig. 2 report: (config, minus, label)
PAIRS_ALL = [("hybrid_strict", "hybrid_published", "strict $-$ published"), ("hybrid_cache", "hybrid_published", "cache $-$ published"),
             ("hybrid_published", "classical", "hybrid $-$ classical"), ("hybrid_published", "none", "hybrid $-$ none"),
             ("classical", "signing", "classical $-$ signing"), ("kem_auth", "hybrid_published", "design K $-$ hybrid")]


def _present():
    import pandas as pd
    s = pd.read_csv(ROOT / SS)
    p = pd.read_csv(ROOT / SP)
    cf = set(s.config)
    pairs = set(zip(p.config, p.minus_config))
    return [x for x in CFGS_ALL if x[0] in cf], [x for x in PAIRS_ALL if (x[0], x[1]) in pairs]


CFGS, PAIRS = _present()


def sitl_numbers(c, doc):
    """Software in the loop, mission model and replay rule numbers, and the text that uses them."""
    q = 'profile == "sik" and config == "{k}" and metric == "{m}"'
    keys = {k for k, _ in CFGS}

    def v(cid, k, m, col="value", fmt="{:.3f}", label="SITL measured", scale=1.0):
        return c(cid, SS, col, q.format(k=k, m=m), fmt=fmt, label=label, scale=scale, doc=doc)
    t = {}
    for k, _ in CFGS:
        t[f"{k}_av"] = v(f"cs_{k}_av", k, "availability_rt_all")
        t[f"{k}_av_lo"] = v(f"cs_{k}_av_lo", k, "availability_rt_all", "ci_lo")
        t[f"{k}_av_hi"] = v(f"cs_{k}_av_hi", k, "availability_rt_all", "ci_hi")
        if k != "none":
            t[f"{k}_lat"] = v(f"cs_{k}_lat", k, "added_latency_rt_ms", fmt="{:.1f}")
        if k in ("classical", "hybrid_published", "hybrid_strict", "hybrid_cache", "kem_auth"):
            t[f"{k}_hs"] = v(f"cs_{k}_hs", k, "handshake_median_s", fmt="{:.2f}", label="emulated")
    t["n_miss"] = c("cs_n_miss", SS, "value", 'profile == "sik" and metric == "missions_completed"', "min", "{:.0f}", label="SITL measured", doc=doc)
    t["cmd_min"] = c("cs_cmd_min", SS, "value", 'profile == "sik" and metric == "commands"', "min", "{:.0f}", label="SITL measured", doc=doc)
    t["cmd_max"] = c("cs_cmd_max", SS, "value", 'profile == "sik" and metric == "commands"', "max", "{:.0f}", label="SITL measured", doc=doc)

    def pd_(cid, a, b, col="difference", fmt="{:+.4f}", scale=1.0):
        return "\\mbox{" + c(cid, SP, col, f'profile == "sik" and config == "{a}" and minus_config == "{b}" and metric == "availability_rt_all"',
                               fmt=fmt, label="SITL measured", scale=scale, doc=doc) + "}"
    for a, b, _ in PAIRS:
        k = f"d_{a}_{b}"
        t[k] = pd_("cs_" + k, a, b)
        t[k + "_lo"] = pd_("cs_" + k + "_lo", a, b, "ci_lo")
        t[k + "_hi"] = pd_("cs_" + k + "_hi", a, b, "ci_hi")
    t["strict_loss"] = pd_("cs_strict_loss", "hybrid_strict", "hybrid_published", fmt="{:.3f}", scale=-1.0)
    t["strict_loss_lo"] = pd_("cs_strict_loss_lo", "hybrid_strict", "hybrid_published", "ci_hi", fmt="{:.3f}", scale=-1.0)
    t["strict_loss_hi"] = pd_("cs_strict_loss_hi", "hybrid_strict", "hybrid_published", "ci_lo", fmt="{:.3f}", scale=-1.0)
    t["pq_drop"] = pd_("cs_pq_drop", "pqsig_real", "hybrid_published", fmt="{:.2f}", scale=-1.0)

    def rj(cid, k, reason, scope="stream commands not acknowledged within 0.5 s", label="SITL measured"):
        return c(cid, SR, "count", f'profile == "sik" and config == "{k}" and scope == "{scope}" and reason == "{reason}"',
                 fmt="{:.0f}", label=label, doc=doc)
    t["strict_nosession"] = rj("cs_strict_nosession", "hybrid_strict", "no_session")
    t["strict_ahead"] = rj("cs_strict_ahead", "hybrid_strict", "rejected_ahead_of_next")
    t["pub_late"] = rj("cs_pub_late", "hybrid_published", "rejected_late_or_duplicate")
    t["resync"] = rj("cs_resync", "hybrid_strict", "all triggers", "resynchronisations (strict rule)", "emulated")
    t["resync_gu"] = rj("cs_resync_gu", "hybrid_strict", "ground_give_up", "resynchronisations (strict rule)", "emulated")
    t["reorder_depth"] = c("cs_reorder_depth", SO, "max_reorder_depth", 'profile == "sik"', "max", "{:.0f}", label="emulated", doc=doc)
    t["pq_model"] = c("cs_pq_model", SC, "mission_model_estimated", 'profile == "sik" and config == "pqsig_real"', fmt="{:.3f}", label="estimated", doc=doc)
    t["m_strict_60"] = c("cs_m_strict_60", MO, "diff_vs_published_mean",
                         'vehicle == "drone" and arch == "B" and link == "sik" and replay_rule == "strict" and over_outage_rate_per_h == 60',
                         fmt="{:+.4f}", label="estimated", doc=doc)
    t["m_rate"] = c("cs_m_rate", MO, "over_outage_rate_per_h",
                    'vehicle == "drone" and arch == "B" and link == "sik" and replay_rule == "strict" and over_outage_rate_per_h == 60',
                    fmt="{:.0f}", label="assumption", doc=doc)
    for dl in (0.55, 0.75, 1.0):
        t[f"pq_dl_{dl}"] = c(f"cs_pq_dl_{str(dl).replace('.', '')}", SD, "availability_rt_all", f'profile == "sik" and config == "pqsig_real" and deadline_s == {dl}',
                             fmt="{:.3f}", label="SITL measured", doc=doc)
    vq = 'profile == "sik" and operation == "vehicle_tag"'
    t["hx_tag"] = c("cs_hx_tag", SH, "host_exceeds_rtl_delay", vq, "sum", "{:,.0f}", label="host measured", doc=doc)
    t["hx_tag_n"] = c("cs_hx_tag_n", SH, "count", vq, "sum", "{:,.0f}", label="host measured", doc=doc)
    t["hx_tag_max"] = c("cs_hx_tag_max", SH, "host_exceeds_rtl_delay", vq, "max", "{:,.0f}", label="host measured", doc=doc)
    t["hx_chk"] = c("cs_hx_chk", SH, "host_exceeds_rtl_delay", 'profile == "sik" and operation == "vehicle_tag_check"', "sum", "{:,.0f}",
                    label="host measured", doc=doc)

    rows = []
    for k, name in CFGS:
        hs = t.get(f"{k}_hs", "--")
        lat = t.get(f"{k}_lat", "ref.")
        if k == "signing":
            name += "$^{a}$"
        rows.append(f"{name} & {hs} & {lat} & {t[k + '_av']} [{t[k + '_av_lo']}, {t[k + '_av_hi']}] \\\\")
    table = r"""\begin{table*}[t]
\centering
\caption{ArduPilot in the loop over an emulated SiK class radio, """ + t["n_miss"] + r""" paired missions per configuration}
\label{tab:sitl}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{lrrr}
\toprule
Configuration & Handshake (s) & Added round trip (ms) & Share acknowledged within 0.5~s [95\% CI] \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}

\smallskip\footnotesize Handshake: median, emulated link and executed cryptography with RTL derived vehicle delays. Added round trip: median round trip to the flight stack's acknowledgement against no authentication (SITL measured). Acknowledged share includes one outage per mission. $^{a}$ signing inside ArduPilot and the ground station at host speed, without RTL derived delays.
\end{table*}
"""
    s = {}
    k_sent = ""
    if "kem_auth" in keys:
        k_sent = (" Design K completes its handshake in " + t["kem_auth_hs"] + "~s and differs from the hybrid session by "
                  + t["d_kem_auth_hybrid_published"] + " (" + t["d_kem_auth_hybrid_published_lo"] + " to " + t["d_kem_auth_hybrid_published_hi"] + "); it was flown after the other configurations, alone on the host, on the same seeds.")
    s["abstract"] = ("With ArduPilot in the loop over an emulated telemetry radio and real cryptography, the hybrid session keeps the share of commands acknowledged within 0.5~s, outages included, at "
                     + t["hybrid_published_av"] + " against " + t["none_av"] + " without authentication, while a signature per command drops it to "
                     + t["pqsig_real_av"] + ", a figure that moves to " + t["pq_dl_1.0"] + " at a 1~s deadline. A strict next counter rule loses "
                     + t["strict_loss"] + " of the acknowledged share on paired seeds, mostly through resynchronisations after outages; a replay cache loses nothing.")
    s["method"] = ("The configurations fly " + t["n_miss"] + " missions each on the same seeds, so they see the same outages and command phases. "
                   "Acknowledged shares carry bootstrap intervals over missions, and differences between configurations are paired by mission; "
                   "the number of commands per configuration ranges from " + t["cmd_min"] + " to " + t["cmd_max"] + ". "
                   "The host was slower than the applied delay for " + t["hx_tag"] + " of " + t["hx_tag_n"] + " vehicle side tags (at most "
                   + t["hx_tag_max"] + " in one configuration) and " + t["hx_chk"] + " tag checks; these are counted, not corrected. "
                   "For comparison, a mission model of the same traffic with independent loss and Poisson outages (" + t["m_rate"] + " per hour, about one per mission) gives availability per rule; "
                   "its strict rule adds a stall per resynchronisation but neither the airtime of the new handshake nor rejections of reordered frames.")
    fig = ("\\begin{figure}[t]\n\\centering\n\\includegraphics[width=\\columnwidth]{fig_sitl.pdf}\n"
           "\\caption{Left: paired differences of the share acknowledged within 0.5~s with 95\\% intervals over missions (SITL measured). "
           "Right: share acknowledged against the deadline (SITL measured, the same runs).}\n"
           "\\label{fig:sitl}\n\\end{figure}\n")
    s["section"] = (table + fig + "Table~\\ref{tab:sitl} and Fig.~\\ref{fig:sitl} show that once a session exists, its per message cost is that of the shipped tag: the hybrid session adds "
                    + t["hybrid_published_lat"] + "~ms to the median command round trip, the classical session " + t["classical_lat"] + "~ms and signing as shipped "
                    + t["signing_lat"] + "~ms, the last through a different mechanism. The hybrid handshake takes " + t["hybrid_published_hs"] + "~s over the emulated radio against "
                    + t["classical_hs"] + "~s for the classical session, a cost paid once per session." + k_sent + " The paired differences resolve a small cost of the hybrid session: "
                    + t["d_hybrid_published_none"] + " (" + t["d_hybrid_published_none_lo"] + " to " + t["d_hybrid_published_none_hi"] + ") against no authentication and "
                    + t["d_hybrid_published_classical"] + " (" + t["d_hybrid_published_classical_lo"] + " to " + t["d_hybrid_published_classical_hi"] + ") against the classical session.\n\n"
                    "A signature on every command adds " + t["pqsig_real_lat"] + "~ms to each round trip, which puts the median round trip next to the deadline: "
                    + t["pqsig_real_av"] + " of its commands are acknowledged within 0.5~s, " + t["pq_dl_0.55"] + " within 0.55~s, " + t["pq_dl_0.75"] + " within 0.75~s and "
                    + t["pq_dl_1.0"] + " within 1~s, against a drop of " + t["pq_drop"] + " from the hybrid session at 0.5~s. The mission model gives " + t["pq_model"]
                    + " at 0.5~s; we have not resolved this difference and report only the measured value.\n\n"
                    "The replay rule matters as much as the algorithms once a session exists. Link layer retransmission delivers some frames after newer ones (reordering depth up to "
                    + t["reorder_depth"] + "), and the published rule rejected " + t["pub_late"] + " of them as late. The strict rule loses " + t["strict_loss"]
                    + " of the acknowledged share against the published rule (paired 95\\% CI " + t["strict_loss_lo"] + " to " + t["strict_loss_hi"] + "). Its cost comes mainly from resynchronisation, not from reordering: "
                    + t["strict_nosession"] + " commands were lost while no session existed during " + t["resync"] + " resynchronisations, " + t["resync_gu"]
                    + " of them triggered when the link layer gave up a frame during an outage, against " + t["strict_ahead"] + " rejected as ahead of the expected counter. "
                    "The replay cache accepted the reordered frames that the published rule rejected: its difference to the published rule is "
                    + t["d_hybrid_cache_hybrid_published"] + " (" + t["d_hybrid_cache_hybrid_published_lo"] + " to " + t["d_hybrid_cache_hybrid_published_hi"]
                    + "), a small gain. The mission model puts the strict rule cost at " + t["m_strict_60"]
                    + ", outside the paired interval; it underestimates the cost because it omits the airtime of the new handshake and the rejections.")
    s["formal"] = ("For out of order delivery, a replay cache proves injective agreement on commands when the vehicle checks and records each pair of session and counter in one step and never forgets an entry, "
                   "a condition stated in the model as a restriction, not derived. When concurrent branches read a table before either records, the model gives a counterexample, and a table read in sequence could not be proved; "
                   "an implementation must therefore check and record atomically. The cache in the flights uses a bounded window, which was proved only on the command layer for a window of two counters, "
                   "and the published timestamp rule could not be proved.")
    s["conclusion"] = "the availability of the shipped tag almost unchanged, while a signature per command does not at a 0.5~s deadline."
    return t, s


def build(claim):
    """Return [(path, text)] for the two versions of the conference paper."""
    write_derived()
    out = []
    for doc, anon in ((DOC, False), (DOC_ANON, True)):
        n = numbers(claim, doc)
        _, s = sitl_numbers(claim, doc)
        out.append((doc, text(n, s, anon)))
    (ROOT / "docs/conference").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs/conference/references.bib").write_text(bib(), encoding="utf-8")
    return out
