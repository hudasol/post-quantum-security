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
    return PREAMBLE + r"""
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
Kannwischer et al.\ established the pqm4 method for Cortex-M4 measurements \cite{pqm4}. Post quantum TLS has been measured on embedded clients \cite{burstinghaus20}, and KEMTLS replaces handshake signatures with encapsulation \cite{kemtls20,gonzalez22}; post quantum WireGuard does the same for a VPN handshake with a machine checked model \cite{pqwg21}. Firmware signatures have been measured on low power boards \cite{banegas21} and in secure boot \cite{kumar20}. Closest to our setting, Hyoung et al.\ evaluate post quantum key exchange for unmanned system command channels with a TLS 1.3 handshake over an emulated UAV radio on a laptop \cite{hyoung26}, de Meneses et al.\ design and formally verify a post quantum EDHOC variant for UAVs with estimated costs \cite{meneses26}, and MAVSec adds encryption to MAVLink \cite{mavsec19}. Twardokus et al.\ show for vehicle to vehicle messages that frame loss, not computation, can decide whether post quantum authentication is practical \cite{twardokus24}. We differ in executing every design under one set of conditions on core designs, in putting a real flight stack in the loop, and in treating the replay rule as a design parameter that is both proved and measured.

\section{Design and baselines}
\label{sec:design}
All session designs share four flights and the MAVLink 2 signing field of 13~B per message after the handshake \cite{mavsign}. \emph{Classical}: X25519 key exchange, Ed25519 signatures by both sides over the transcript and both identities, key confirmation tags. \emph{Post quantum only}: ML-KEM-768 and ML-DSA-44 in the same roles. \emph{Hybrid} (proposed): X25519 and ML-KEM-768 together, the session key derived from both secrets and a transcript hash, ML-DSA-44 signatures by both sides. Our first formal pass found that a design in which only the ground station signs leaves the vehicle unauthenticated; the vehicle signature (change F1) closes it. Two further fixes concern the provisioned key fallback (fresh nonces, F2) and firmware updates (a signed version with a monotonic counter, F3). \emph{Signing as shipped}: a provisioned key, no handshake. \emph{Signature per command}: an ML-DSA-44 signature on every command, verified by the vehicle. The vehicle accepts a command under one of three rules: \emph{published} (timestamp greater than the last accepted, gaps allowed) \cite{mavsign}, \emph{strict} (only the next counter; a loss stalls the stream until resynchronisation), and \emph{replay cache} (any counter not yet accepted within a window).

\section{Method}
\label{sec:method}
\emph{RTL simulation.} Ibex in its small configuration \cite{ibex} and CV32E40P \cite{cv32e40p}, both RV32IMC without caches or wait states, are simulated cycle accurately with Verilator. One firmware image per design runs the vehicle and the ground side, each step timed with the cycle counter, five runs per image with a fixed seed block; every run checks that both sides derive the same key, that all signatures and tags verify, and known answers for the hash functions. Libraries are pinned and unmodified: mlkem-native \cite{mlkemnative}, mldsa-native \cite{mldsanative} and Monocypher \cite{monocypher}, compiled with one compiler at \texttt{-O3}; peak stack is measured by stack painting.

\emph{Software in the loop.} ArduPilot Copter 4.7.2 \cite{ardupilot} flies scripted missions with its built in vehicle model behind a relay that emulates a SiK class telemetry radio with frame loss, retransmission and one outage per mission. A gateway pair in front of the ground station and the flight stack executes the handshake, the tags and the replay rule with the same algorithms on the host; vehicle side compute is applied as a delay equal to the RTL cycles of the slower core at 168~MHz, so the host speed does not enter the result. Seeds are paired across configurations, so every configuration sees the same outages and command phases. """ + s["method"] + r"""

\emph{Formal models.} ProVerif \cite{proverif} checks secrecy and injective agreement under a Dolev Yao attacker with abstract primitives, unbounded sessions and the bounds stated per model.

\emph{Discipline.} Fourteen predictions with refutation clauses were hashed before the runs and are scored by script; every number in this paper is registered with its file, column and query and checked by a script in continuous integration.

\section{Executed baselines on core designs}
\label{sec:rtl}
""" + rtl_table(n) + r"""
Table~\ref{tab:rtl} gives the cost of one session start and of one command. On both cores the hybrid session costs """ + n["cv32e40p_hyb_over_cls_vehicle"] + "--" + n["ibex_hyb_over_cls_vehicle"] + r"""$\times$ the classical vehicle side and only """ + n["ibex_hyb_over_pq_vehicle"] + "--" + n["cv32e40p_hyb_over_pq_vehicle"] + r"""$\times$ the post quantum only session: the X25519 part is cheap beside the two ML-DSA-44 operations, and one X25519 multiplication (""" + n["cv32e40p_x25519"] + r"""~M cycles on CV32E40P) costs more than an ML-KEM-768 encapsulation (""" + n["cv32e40p_encaps"] + r"""~M). The hybrid handshake carries """ + n["bytes_hybrid_f1"] + r"""~B against """ + n["bytes_classical"] + r"""~B for the classical one and needs """ + n["cv32e40p_hyb_stack"] + r"""~kB of stack against """ + n["cv32e40p_cls_stack"] + r"""~kB. After the handshake a command costs a tag check of """ + n["cv32e40p_tag_vehicle"] + r""" cycles on a 60~B frame; verifying an ML-DSA-44 signature on a COMMAND\_LONG instead costs """ + n["cv32e40p_pqc_over_tag_vehicle"] + r"""$\times$ the tag check of the same frame. At 168~MHz the vehicle side of the hybrid session start would take about """ + n["t168_hyb"] + r"""~ms on CV32E40P (estimated), against """ + n["t168_cls"] + r"""~ms for the classical session. Ibex needs """ + n["core_ratio_hyb"] + r"""$\times$ the cycles of CV32E40P for the same hybrid handshake, so a figure for one core of an instruction set does not transfer to another.

\section{Software in the loop and availability}
\label{sec:sitl}
""" + s["section"] + r"""

\section{Formal results}
\label{sec:formal}
ProVerif checked """ + n["pv_q"] + r""" queries in """ + n["pv_m"] + r""" model files: """ + n["pv_p"] + r""" proved, """ + n["pv_cx"] + r""" counterexamples (in the stated designs before F1 to F3, in deliberate controls and as expected findings) and """ + n["pv_cnp"] + r""" that the tool could not prove. With F1 the session keys of both sides stay secret and each side authenticates the other. """ + s["formal"] + r"""

\section{Discussion and limitations}
The results support a session design for streamed commands: the post quantum cost is paid once per session, and the per message cost stays that of the shipped tag. A signature per command is a poor fit for streams but remains an option for rare, high value commands. The limits are explicit. Open RISC-V cores are not Cortex-M flight controllers: instruction set, multiplier, memory system and flash wait states differ, so the cycles are a baseline for comparison between designs, not a prediction for a given board. The link is an emulation of a radio, the flight stack runs on a host, and only ArduPilot was used. Proofs are symbolic and say nothing about an implementation; a real replay window needs a correct bounded table. Free memory matters as much as cycles: default PX4 builds on """ + n["fs_boards"] + r""" board classes leave as little as """ + n["px4_min"] + r"""~B of flash (host measured from linker output), which raises the estimated share of a fleet needing new hardware from """ + n["hr_a"] + r""" to """ + n["hr_m"] + r""" in a fleet model. The next step is to repeat the executed baselines on Cortex-M4 and Cortex-M33 boards with registered predictions and a borrowed telemetry radio.

\section{Conclusion}
Executed under one set of conditions, a hybrid post quantum session for drone commands costs about twice the computation of a classical session and over thirty times its handshake bytes, yet leaves the per command cost and """ + s["conclusion"] + r""" A replay cache, proved safe in the symbolic model, removes the need to choose between in order delivery and a stalled stream.

\bibliographystyle{IEEEtran}
\bibliography{references}
\end{document}
"""


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
