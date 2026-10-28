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
    for d in ("classical", "pq_only", "hybrid_f1"):
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
        for side in ("vehicle", "ground"):
            n[f"{core}_tag_{side}"] = c(f"cf_{core}_tag_{side}", SES, "cycles_median",
                                        f'core == "{core}" and design == "mavlink_tag" and unit == "per message, tag alone, 60 B frame" and side == "{side}"',
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
    for d in ("classical", "pq_only", "hybrid_f1"):
        for fl in ("f1", "f2", "f3", "f4"):
            n[f"{d}_{fl}"] = c(f"cf_{d}_{fl}", DER, "value", f'core == "cv32e40p" and ratio == "{d}_{fl}_bytes"', fmt="{:,.0f}", label="RTL simulated", doc=doc)
    PS = "data/predictions_v6_scores.csv"
    n["q_n"] = c("cf_q_n", PS, "id", aggregate="count", label="host measured", doc=doc)
    for vv in ("hit", "between", "miss"):
        n[f"q_{vv}"] = c(f"cf_q_{vv}", PS, "id", f'verdict == "{vv}"', "count", label="host measured", doc=doc)
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


PREAMBLE = r"""\documentclass[conference]{IEEEtran}
\pdfsuppressptexinfo=-1
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
    """The paper. n: RTL, formal and fleet numbers; s: software in the loop and mission numbers."""
    meta = "" if anon else "\\pdfinfo{/Author (Huda Mueen)}\n"
    return PREAMBLE + meta + r"""
\title{Post Quantum Session Authentication for Drone Command Links: Executed Baselines, Software in the Loop and Replay Rules}
""" + authors(anon) + r"""
\maketitle

\begin{abstract}
Drones and ground robots authenticate commands over narrow radio links with keys that a quantum adversary may later recover. Published work measures post quantum primitives on microcontrollers or post quantum TLS on hosts; it rarely compares complete command channel designs under one set of conditions, with the flight stack in the loop and with the replay rule that decides availability. We execute five designs end to end, from MAVLink 2 signing as shipped to a hybrid session (X25519 plus ML-KEM-768, ML-DSA-44 signatures by both sides) and a signature on every command, on two open RISC-V core designs in cycle accurate RTL simulation, and run them with real cryptography in front of ArduPilot in software in the loop over an emulated telemetry radio. The hybrid session costs """ + n["cv32e40p_hyb_over_cls_vehicle"] + r""" to """ + n["ibex_hyb_over_cls_vehicle"] + r""" times the vehicle side computation of a classical session of the same shape, while a signature per command costs """ + n["cv32e40p_pqc_over_tag_vehicle"] + r""" to """ + n["ibex_pqc_over_tag_vehicle"] + r""" times a per message tag. """ + s["abstract"] + r""" ProVerif proves injective agreement on commands for a replay cache that accepts out of order delivery. """ + artifact(anon) + r"""
\end{abstract}

\section{Introduction}
A small multirotor runs its flight stack on a microcontroller and receives commands over a telemetry radio of tens of kilobits per second. MAVLink 2, the common protocol, offers a per message tag with a pre shared key \cite{mavsign}; key establishment and endpoint authentication are left to the operator, and classical public key schemes used for them are threatened by a future quantum computer. The replacements are standardised: ML-KEM for key establishment \cite{fips203} and ML-DSA for signatures \cite{fips204}.

What an engineer cannot yet answer from published evidence is how a complete post quantum command channel compares with the classical and the shipped alternatives on the same device, the same link and the same flight stack, and what the replay rule that the protocol needs does to availability. Primitive benchmarks on Cortex-M cores \cite{pqm4} and post quantum TLS on embedded or host systems \cite{burstinghaus20,gonzalez22,hyoung26} answer parts of this; formal analyses of drone handshakes rarely include the per message layer.

This paper contributes:
(1) executed baselines of five command channel designs on two open RISC-V core designs in cycle accurate RTL simulation, with correctness checks, stack and code size, under identical compiler and libraries (Section~\ref{sec:rtl});
(2) software in the loop runs of ArduPilot with a gateway that executes the real handshakes and per message tags, three replay rules on paired seeds, and a mission model per rule (Section~\ref{sec:sitl});
(3) ProVerif models of the hybrid session with three design fixes and of replay rules that accept out of order delivery (Section~\ref{sec:formal});
(4) a pre registered, script checked method in which every number in this paper is read from a committed result file.

\section{Related work}
Kannwischer et al.\ established the pqm4 method for Cortex-M4 measurements \cite{pqm4}. Post quantum TLS has been measured on embedded clients \cite{burstinghaus20}, and KEMTLS replaces handshake signatures with encapsulation \cite{kemtls20,gonzalez22}; post quantum WireGuard does the same for a VPN handshake with a machine checked model \cite{pqwg21}. Firmware signatures have been measured on low power boards \cite{banegas21} and in secure boot \cite{kumar20}. Closest to our setting, Hyoung et al.\ evaluate post quantum key exchange for unmanned system command channels with a TLS 1.3 handshake over an emulated UAV radio on a laptop \cite{hyoung26}, de Meneses et al.\ design and formally verify a post quantum EDHOC variant for UAVs with estimated costs \cite{meneses26}, and MAVSec adds encryption to MAVLink \cite{mavsec19}. Twardokus et al.\ show for vehicle to vehicle messages that frame loss, not computation, can decide whether post quantum authentication is practical \cite{twardokus24}. Table~\ref{tab:rw} compares the closest of them with this paper. We differ in executing every design under one set of conditions on core designs, in putting a real flight stack in the loop, and in treating the replay rule as a design parameter that is both proved and measured.


\begin{table*}[t]
\centering
\caption{Closest prior work and this paper (as described in each source)}
\label{tab:rw}
\setlength{\tabcolsep}{2pt}
\footnotesize
\begin{tabular}{lllll}
\toprule
Work & Platform & Link and stack & Replay rule & Formal \\
\midrule
\cite{hyoung26} & x86 laptop & emulated UAV radio, TLS 1.3 proxy & not studied & none \\
\cite{burstinghaus20} & ESP32, Cortex-A53, others & Ethernet or Wi-Fi, TLS & not studied & none \\
\cite{kemtls20} & Xeon server & emulated network, TLS & not studied & proof on paper \\
\cite{meneses26} & estimated costs & UAV, EDHOC variant & not studied & Tamarin \\
\cite{twardokus24} & V2V chipset & DSRC, simulated and on road & not applicable & proof on paper \\
This paper & two RISC-V core designs (RTL), host & emulated SiK radio, ArduPilot in the loop & three rules, measured and proved & ProVerif \\
\bottomrule
\end{tabular}
\end{table*}
\section{Design and baselines}
\label{sec:design}
All session designs share four flights and the MAVLink 2 signing field of 13~B per message after the handshake \cite{mavsign}. \emph{Classical}: X25519 key exchange, Ed25519 signatures by both sides over the transcript and both identities, key confirmation tags. \emph{Post quantum only}: ML-KEM-768 and ML-DSA-44 in the same roles. \emph{Hybrid} (proposed): X25519 and ML-KEM-768 together, the session key derived from both secrets and a transcript hash, ML-DSA-44 signatures by both sides. Our first formal pass found that a design in which only the ground station signs leaves the vehicle unauthenticated; the vehicle signature (change F1) closes it. Two further fixes concern the provisioned key fallback (fresh nonces, F2) and firmware updates (a signed version with a monotonic counter, F3). Table~\ref{tab:flights} gives the bytes of each flight. \emph{Signing as shipped}: a provisioned key, no handshake. \emph{Signature per command}: an ML-DSA-44 signature on every command, verified by the vehicle. The vehicle accepts a command under one of three rules: \emph{published} (timestamp greater than the last accepted, gaps allowed) \cite{mavsign}, \emph{strict} (only the next counter; a loss stalls the stream until resynchronisation), and \emph{replay cache} (any counter not yet accepted within a window).

\begin{table}[t]
\centering
\caption{Bytes per handshake flight as built by the executed protocols}
\label{tab:flights}
\setlength{\tabcolsep}{4pt}
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
\emph{RTL simulation.} Ibex in its small configuration \cite{ibex} and CV32E40P \cite{cv32e40p}, both RV32IMC without caches or wait states, are simulated cycle accurately with Verilator. One firmware image per design runs the vehicle and the ground side, each step timed with the cycle counter, five runs per image with a fixed seed block; every run checks that both sides derive the same key, that all signatures and tags verify, and known answers for the hash functions. Libraries are pinned and unmodified: mlkem-native \cite{mlkemnative}, mldsa-native \cite{mldsanative} and Monocypher \cite{monocypher}, compiled with one compiler at \texttt{-O3}; peak stack is measured by stack painting.

\emph{Software in the loop.} ArduPilot Copter 4.7.2 \cite{ardupilot} flies scripted missions with its built in vehicle model behind a relay that emulates a SiK class telemetry radio with frame loss, retransmission and one outage per mission. A gateway pair in front of the ground station and the flight stack executes the handshake, the tags and the replay rule with the same algorithms on the host; vehicle side compute is applied as a delay equal to the RTL cycles of the slower core at 168~MHz, so the host speed does not enter the result. Seeds are paired across configurations, so every configuration sees the same outages and command phases. """ + s["method"] + r"""

\emph{Formal models.} ProVerif \cite{proverif} checks secrecy and injective agreement under a Dolev Yao attacker with abstract primitives, unbounded sessions and the bounds stated per model.

\emph{Discipline.} """ + n["q_n"] + r""" predictions with refutation clauses were hashed before the runs and scored by script under the less favourable reading of any ambiguous clause: """ + n["q_hit"] + r""" hit, """ + n["q_between"] + r""" between and """ + n["q_miss"] + r""" missed (the miss: a seen counter table read by concurrent branches gives a counterexample, so the cache must check and record in one step). Every number in this paper is registered with its file, column and query and checked by a script in continuous integration.

\section{Executed baselines on core designs}
\label{sec:rtl}
""" + rtl_table(n) + r"""
\begin{figure}[t]
\centering
\includegraphics[width=\columnwidth]{fig_rtl.pdf}
\caption{Million cycles of one session start per design, vehicle and ground side (RTL simulated, median of five runs).}
\label{fig:rtl}
\end{figure}
Table~\ref{tab:rtl} and Fig.~\ref{fig:rtl} give the cost of one session start and of one command. On both cores the hybrid session costs """ + n["cv32e40p_hyb_over_cls_vehicle"] + "--" + n["ibex_hyb_over_cls_vehicle"] + r"""$\times$ the classical vehicle side and only """ + n["ibex_hyb_over_pq_vehicle"] + "--" + n["cv32e40p_hyb_over_pq_vehicle"] + r"""$\times$ the post quantum only session: the X25519 part is cheap beside the two ML-DSA-44 operations, and one X25519 multiplication (""" + n["cv32e40p_x25519"] + r"""~M cycles on CV32E40P) costs more than an ML-KEM-768 encapsulation (""" + n["cv32e40p_encaps"] + r"""~M). The hybrid handshake carries """ + n["bytes_hybrid_f1"] + r"""~B against """ + n["bytes_classical"] + r"""~B for the classical one and needs """ + n["cv32e40p_hyb_stack"] + r"""~kB of stack against """ + n["cv32e40p_cls_stack"] + r"""~kB. After the handshake a command costs a tag check of """ + n["cv32e40p_tag_vehicle"] + r""" cycles on a 60~B frame; verifying an ML-DSA-44 signature on a COMMAND\_LONG instead costs """ + n["cv32e40p_pqc_over_tag_vehicle"] + r"""$\times$ the tag check of the same frame. At 168~MHz the vehicle side of the hybrid session start would take about """ + n["t168_hyb"] + r"""~ms on CV32E40P (estimated), against """ + n["t168_cls"] + r"""~ms for the classical session. Ibex needs """ + n["core_ratio_hyb"] + r"""$\times$ the cycles of CV32E40P for the same hybrid handshake, so a figure for one core of an instruction set does not transfer to another.

\section{Software in the loop and availability}
\label{sec:sitl}
""" + s["section"] + r"""

\section{Formal results}
\label{sec:formal}
ProVerif checked """ + n["pv_q"] + r""" queries in """ + n["pv_m"] + r""" model files: """ + n["pv_p"] + r""" proved, """ + n["pv_cx"] + r""" counterexamples (in the stated designs before F1 to F3, in deliberate controls and as expected findings) and """ + n["pv_cnp"] + r""" that the tool could not prove. With F1 the session keys of both sides stay secret and each side authenticates the other. """ + s["formal"] + r"""

\section{Discussion and limitations}
The results support a session design for streamed commands: the post quantum cost is paid once per session, and the per message cost stays that of the shipped tag. A signature per command is a poor fit for streams but remains an option for rare, high value commands. The limits are explicit. Open RISC-V cores are not Cortex-M flight controllers: instruction set, multiplier, memory system and flash wait states differ, so the cycles are a baseline for comparison between designs, not a prediction for a given board. The link is an emulation of a radio, the flight stack runs on a host, and only ArduPilot was used. Proofs are symbolic and say nothing about an implementation; a real replay window needs a correct bounded table. Free memory matters as much as cycles: default PX4 builds on """ + n["fs_boards"] + r""" board classes leave as little as """ + n["px4_min"] + r"""~B of flash (host measured from linker output), which raises the estimated share of a fleet needing new hardware from """ + n["hr_a"] + r""" to """ + n["hr_m"] + r""" in a fleet model. \emph{Threats to validity.} (i) Cycles come from two open core designs with ideal single cycle memories; Cortex-M flight controllers have flash wait states and caches. (ii) In the loop, vehicle side compute is a delay derived from those cycles at an assumed 168~MHz; the host was slower than that delay for a small share of per message tags, which we count but do not correct. (iii) The radio is an emulation with independent frame loss and one scripted outage per mission; real loss is bursty. (iv) Twenty missions per configuration give intervals of a few hundredths for the acknowledged share, so only the strict rule and per command signature effects are resolved. (v) Prior work numbers are not comparable to ours because platforms and links differ; Table~\ref{tab:rw} compares designs and methods, not figures. (vi) All reviews of this study were internal, not by independent groups. The next step is to repeat the executed baselines on Cortex-M4 and Cortex-M33 boards with registered predictions and a borrowed telemetry radio.

\section{Conclusion}
Executed under one set of conditions, a hybrid post quantum session for drone commands costs about twice the computation of a classical session and over thirty times its handshake bytes, yet leaves the per command cost and """ + s["conclusion"] + r""" A replay cache, proved safe in the symbolic model, removes the need to choose between in order delivery and a stalled stream.

\bibliographystyle{IEEEtran}
\bibliography{references}
\end{document}
"""


def flights_rows(n):
    return "\n".join(f"{name} & {n[d + '_f1']} & {n[d + '_f2']} & {n[d + '_f3']} & {n[d + '_f4']} & {n['bytes_' + d]} \\\\"
                     for d, name in (("classical", "Classical"), ("pq_only", "PQ only"), ("hybrid_f1", "Hybrid, F1")))


def rtl_table(n):
    rows = [("MAVLink 2 tag, 60~B$^{a}$", n["ibex_tag_vehicle"], n["cv32e40p_tag_vehicle"], n["ibex_tag_ground"], n["cv32e40p_tag_ground"]),
            ("Classical session", n["ibex_classical_vehicle"], n["cv32e40p_classical_vehicle"], n["ibex_classical_ground"], n["cv32e40p_classical_ground"]),
            ("PQ only session", n["ibex_pq_only_vehicle"], n["cv32e40p_pq_only_vehicle"], n["ibex_pq_only_ground"], n["cv32e40p_pq_only_ground"]),
            ("Hybrid session, F1", n["ibex_hybrid_f1_vehicle"], n["cv32e40p_hybrid_f1_vehicle"], n["ibex_hybrid_f1_ground"], n["cv32e40p_hybrid_f1_ground"]),
            ("ML-DSA-44 per command", n["ibex_pqc_v"], n["cv32e40p_pqc_v"], "--", "--")]
    body = "\n".join(f"{a} & {b} & {c} & {d} & {e} \\\\" for a, b, c, d, e in rows)
    return r"""\begin{table}[t]
\centering
\caption{Executed baselines, million cycles per unit (RTL simulated, median of five runs)}
\label{tab:rtl}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{lrrrr}
\toprule
 & \multicolumn{2}{c}{Vehicle} & \multicolumn{2}{c}{Ground} \\
Design & Ibex & CV32E40P & Ibex & CV32E40P \\
\midrule
""" + body + r"""
\bottomrule
\end{tabular}

\smallskip\footnotesize $^{a}$ cycles, not millions: check (vehicle) and generation (ground) of one tag over a 60~B frame.
\end{table}
"""


SS = "sitl/results_r6/summary.csv"
SP = "sitl/results_r6/paired.csv"
SR = "sitl/results_r6/rejections.csv"
SC = "sitl/results_r6/comparison.csv"
MR = "mission/results/replay_base.csv"
CFGS = [("none", "No authentication"), ("signing", "MAVLink 2 signing as shipped"), ("classical", "Classical session"),
        ("hybrid_published", "Hybrid, published rule"), ("hybrid_strict", "Hybrid, strict rule"),
        ("hybrid_cache", "Hybrid, replay cache"), ("pqsig_real", "ML-DSA-44 per command")]


def sitl_numbers(c, doc):
    """Software in the loop, mission model and replay rule numbers, and the text that uses them."""
    q = 'profile == "sik" and config == "{k}" and metric == "{m}"'

    def v(cid, k, m, col="value", fmt="{:.3f}", label="SITL measured", scale=1.0):
        return c(cid, SS, col, q.format(k=k, m=m), fmt=fmt, label=label, scale=scale, doc=doc)
    t = {}
    for k, _ in CFGS:
        t[f"{k}_av"] = v(f"cs_{k}_av", k, "availability_rt_all")
        t[f"{k}_av_lo"] = v(f"cs_{k}_av_lo", k, "availability_rt_all", "ci_lo")
        t[f"{k}_av_hi"] = v(f"cs_{k}_av_hi", k, "availability_rt_all", "ci_hi")
        t[f"{k}_n"] = v(f"cs_{k}_n", k, "missions_completed", fmt="{:.0f}")
        if k != "none":
            t[f"{k}_lat"] = v(f"cs_{k}_lat", k, "added_latency_rt_ms", fmt="{:.1f}")
        if k in ("classical", "hybrid_published", "hybrid_strict", "hybrid_cache"):
            t[f"{k}_hs"] = v(f"cs_{k}_hs", k, "handshake_median_s", fmt="{:.2f}", label="emulated")

    def pd_(cid, a, b, col="difference", fmt="{:+.3f}"):
        return c(cid, SP, col, f'profile == "sik" and config == "{a}" and minus_config == "{b}" and metric == "availability_rt_all"',
                 fmt=fmt, label="SITL measured", doc=doc)
    t["d_strict"] = pd_("cs_d_strict", "hybrid_strict", "hybrid_published")
    t["d_strict_lo"] = pd_("cs_d_strict_lo", "hybrid_strict", "hybrid_published", "ci_lo")
    t["d_strict_hi"] = pd_("cs_d_strict_hi", "hybrid_strict", "hybrid_published", "ci_hi")
    t["d_cache"] = pd_("cs_d_cache", "hybrid_cache", "hybrid_published", fmt="{:+.4f}")
    t["d_cache_lo"] = pd_("cs_d_cache_lo", "hybrid_cache", "hybrid_published", "ci_lo", fmt="{:+.4f}")
    t["d_cache_hi"] = pd_("cs_d_cache_hi", "hybrid_cache", "hybrid_published", "ci_hi", fmt="{:+.4f}")

    def rj(cid, k, reason):
        return c(cid, SR, "count", f'profile == "sik" and config == "{k}" and scope == "stream commands not acknowledged within 0.5 s" and reason == "{reason}"',
                 fmt="{:.0f}", label="SITL measured", doc=doc)
    t["strict_nosession"] = rj("cs_strict_nosession", "hybrid_strict", "no_session")
    t["strict_ahead"] = rj("cs_strict_ahead", "hybrid_strict", "rejected_ahead_of_next")
    t["pub_late"] = rj("cs_pub_late", "hybrid_published", "rejected_late_or_duplicate")
    t["sign_late"] = rj("cs_sign_late", "signing", "not_acknowledged_by_vehicle")
    t["pq_model"] = c("cs_pq_model", SC, "mission_model_estimated", 'profile == "sik" and config == "pqsig_real"', fmt="{:.3f}", label="estimated", doc=doc)
    mq = 'vehicle == "drone" and arch == "B" and link == "sik" and tag == "base" and replay_rule == "{r}"'
    t["m_pub"] = c("cs_m_pub", MR, "avail_mean", mq.format(r="published"), fmt="{:.3f}", label="estimated", doc=doc)
    t["m_strict_d"] = c("cs_m_strict_d", MR, "diff_vs_published_mean", mq.format(r="strict"), fmt="{:+.4f}", label="estimated", doc=doc)

    MO = "mission/results/replay_outage_sweep.csv"
    t["m_strict_60"] = c("cs_m_strict_60", MO, "diff_vs_published_mean",
                         'vehicle == "drone" and arch == "B" and link == "sik" and replay_rule == "strict" and over_outage_rate_per_h == 60',
                         fmt="{:+.4f}", label="estimated", doc=doc)
    rows = []
    for k, name in CFGS:
        hs = t.get(f"{k}_hs", "--")
        lat = t.get(f"{k}_lat", "ref.")
        rows.append(f"{name} & {hs} & {lat} & {t[k + '_av']} [{t[k + '_av_lo']}, {t[k + '_av_hi']}] \\\\")
    table = r"""\begin{table*}[t]
\centering
\caption{ArduPilot in the loop over an emulated SiK class radio, 20 paired missions per configuration}
\label{tab:sitl}
\setlength{\tabcolsep}{3pt}
\begin{tabular}{lrrr}
\toprule
Configuration & Handshake (s) & Added round trip (ms) & Share acknowledged within 0.5~s [95\% CI] \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}

\smallskip\footnotesize Handshake: median, emulated link and executed cryptography with RTL derived delays. Added RTT: median round trip to the flight stack's acknowledgement against no authentication (SITL measured). Acknowledged share includes one outage per mission.
\end{table*}
"""
    s = {}
    s["abstract"] = ("In the loop, the hybrid session keeps the share of commands acknowledged within 0.5~s, outages included, at " + t["hybrid_published_av"]
                     + " against " + t["none_av"] + " without authentication, while a signature per command drops it to " + t["pqsig_real_av"]
                     + ". A strict next counter rule, which earlier proofs assumed, costs " + t["d_strict"].lstrip("+") + " of that share on paired seeds; a replay cache costs nothing measurable.")
    s["method"] = ("Seven configurations fly 20 missions each: no authentication, signing as shipped, the classical session, the hybrid session under each of the three rules, "
                   "and ML-DSA-44 per command; acknowledged shares carry bootstrap intervals over missions, and differences between rules are paired by mission. "
                   "A mission model with 1000 runs per configuration gives availability per rule for comparison.")
    fig = ("\\begin{figure}[t]\n\\centering\n\\includegraphics[width=\\columnwidth]{fig_sitl.pdf}\n"
           "\\caption{Share of commands acknowledged within 0.5~s with one outage per mission, per configuration: ArduPilot in the loop (dots, 95\\% interval over 20 missions) and the mission model (crosses).}\n"
           "\\label{fig:sitl}\n\\end{figure}\n")
    s["section"] = (table + fig + "Table~\\ref{tab:sitl} and Fig.~\\ref{fig:sitl} show that once a session exists, its per message cost is that of the shipped tag: the hybrid session adds "
                    + t["hybrid_published_lat"] + "~ms to the median command round trip against " + t["signing_lat"] + "~ms for signing as shipped. "
                    "Its handshake takes " + t["hybrid_published_hs"] + "~s over the emulated radio against " + t["classical_hs"] + "~s for the classical session, "
                    "a cost paid once per session. A signature on every command adds " + t["pqsig_real_lat"] + "~ms to each round trip, and only "
                    + t["pqsig_real_av"] + " of its commands are acknowledged within the deadline (mission model: " + t["pq_model"] + "), because the deadline falls inside the transfer of a 2.4~kB signature.\n\n"
                    "The replay rule matters more than the algorithms once a session exists. Link layer retransmission delivers some frames after newer ones; the published rule rejected "
                    + t["pub_late"] + " of them as late. The strict next counter rule lost " + t["strict_nosession"] + " commands while it resynchronised and rejected "
                    + t["strict_ahead"] + " that arrived ahead of the expected counter, lowering the acknowledged share by " + t["d_strict"].lstrip("+") + " (paired 95\\% CI "
                    + t["d_strict_lo"] + " to " + t["d_strict_hi"] + "). The replay cache accepted the reordered frames: its difference to the published rule is "
                    + t["d_cache"] + " (" + t["d_cache_lo"] + " to " + t["d_cache_hi"] + "). The mission model, whose link layer delivers in order, puts the strict rule cost at only "
                    + t["m_strict_d"] + " against " + t["m_pub"] + " under the published rule; reordering, which only the flight stack in the loop exposed, is what makes the strict rule expensive. Even in the model the strict rule cost grows with the outage rate, to "
                    + t["m_strict_60"] + " at 60 outages per hour.")
    s["formal"] = ("For out of order delivery, a replay cache that checks and records each (session, counter) pair in one step proves injective agreement on commands with several commands per key, "
                   "while a control without the check and an encoding in which concurrent branches read the table give counterexamples; a bounded window could only be proved on the command layer with help to the tool. "
                   "Together with Section~\\ref{sec:sitl}, this resolves the earlier choice between in order delivery and a stalled stream in favour of a replay cache.")
    s["conclusion"] = "the availability of the shipped tag almost unchanged, while a signature per command does not."
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
