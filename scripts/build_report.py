#!/usr/bin/env python3
"""Assemble docs/REPORT.md from docs/REPORT_body.md.
Macros in the body pull numbers from data/evidence.csv so prose cannot drift from the table:
  {{cyc:ID}} {{stack:ID}} {{code:ID}} {{size:ID}} {{eng:ID}}  -> thousands-separated value of that column
  {{ms:ID}}     -> cycles converted at the two candidate pqm4 clocks in data/pqm4_board_clock.csv (DERIVED)
  {{note_ms:ID}}-> the 'boot time|avg time|mean time X ms' figure from compiler_flags_or_notes
  {{ratio:A/B}} -> cycles(A)/cycles(B) as 'N.NN x'
  {{nrows}}     -> number of evidence rows
  {{INCLUDE:file|old first line|new first line}} -> embed another docs file
  {{APPENDICES}}-> generated appendices
Fails loudly on any missing value."""
import csv, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "data/evidence.csv", encoding="utf-8")))
R = {r["id"]: r for r in rows}

def num(i, col):
    v = R[i][col]
    if v == "":
        sys.exit(f"macro error: {i} has empty {col}")
    return float(v)

def fmt(x):
    return f"{x:,.0f}" if float(x).is_integer() else f"{x:,}"

_rule = {r["key"]: r["value"] for r in csv.DictReader(open(ROOT / "data/pqm4_board_clock.csv", newline="", encoding="utf-8"))}
CLK_HI = int(_rule["candidate_clock_mhz_readme"]); CLK_LO = int(_rule["candidate_clock_mhz_l4r5zi_code"])

def expand(m):
    kind, arg = m.group(1), m.group(2)
    if kind == "cyc": return fmt(num(arg, "cycles"))
    if kind == "stack": return fmt(num(arg, "stack_bytes"))
    if kind == "code": return fmt(num(arg, "flash_or_code_bytes"))
    if kind == "size": return fmt(num(arg, "key_or_sig_size_bytes"))
    if kind == "eng":
        v = num(arg, "energy_uj"); return f"{v:,.1f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"
    if kind == "ms":
        c = num(arg, "cycles")
        return f"{c/CLK_HI/1000:,.1f} ms at {CLK_HI} MHz or {c/CLK_LO/1000:,.1f} ms at {CLK_LO} MHz"
    if kind == "ratio":
        a, b = arg.split("/"); return f"{num(a,'cycles')/num(b,'cycles'):.2f}x"
    if kind == "note_ms":
        mm = re.search(r"(?:boot time|avg time|mean time)\s+([\d.]+)\s*ms", R[arg]["compiler_flags_or_notes"])
        if not mm: sys.exit(f"macro error: no ms in notes of {arg}")
        return mm.group(1)
    sys.exit("unknown macro " + kind)

body = (ROOT / "docs/REPORT_body.md").read_text(encoding="utf-8")
body = re.sub(r"\{\{(cyc|stack|code|size|eng|ms|ratio|note_ms):([^}]+)\}\}", expand, body)
body = body.replace("{{nrows}}", str(len(rows)))

def include(m):
    f, old, new = m.group(1), m.group(2), m.group(3)
    t = (ROOT / "docs" / f).read_text(encoding="utf-8").split("\n")
    if t[0].strip() != old: sys.exit(f"include {f}: first line is {t[0]!r}")
    return "# " + new + "\n" + "\n".join(t[1:])
body = re.sub(r"\{\{INCLUDE:([^|]+)\|([^|]+)\|([^}]+)\}\}", include, body)

# ---------- appendices
def md(s): return str(s).replace("|", "/").replace("\n", " ")
src = {}
for r in rows:
    k = (r["source_title"], r["source_url"], r["retrieval_date"])
    d = src.setdefault(k, {"n": 0, "dev": set()})
    d["n"] += 1; d["dev"].add(r["device_class"])
A = ["# Appendix A. Source register (every source behind a table row)", "",
     "Retrieved on the date shown; `rows` = number of table rows taken from that source. Per-row locations are in `data/evidence.csv`.", ""]
for n, ((t, u, d), v) in enumerate(sorted(src.items(), key=lambda kv: kv[0][0].lower()), 1):
    A.append(f"{n}. {md(t)[:120]} ({v['n']} rows; retrieved {d}) <{u.split(' ')[0]}>")
A.append("")
sel = []
def add(pred):
    for r in rows:
        if pred(r) and r["id"] not in sel: sel.append(r["id"])
add(lambda r: "mupq/pqm4" in r["source_url"] and r["parameter_set"] in ("ML-KEM-768", "ML-DSA-44", "ML-DSA-65"))
add(lambda r: "mupq/pqm4" in r["source_url"] and r["parameter_set"] in ("sphincs-sha2-128s-simple", "sphincs-sha2-128f-simple"))
add(lambda r: r["id"] in ("S2-0254","S2-0257","S2-0316","S2-0319","S2-0322","S2-0354","S2-0355","S2-0347","S2-0349","S2-0351","S2-0353","S2-0356"))
add(lambda r: r["size_kind"] == "standard" and r["scheme"] in ("ML-DSA","ML-KEM") and r["parameter_set"] in ("ML-KEM-768","ML-DSA-44","ML-DSA-65","ML-DSA-87"))
add(lambda r: r["stream"] == "S3")
add(lambda r: r["id"] in ("S2-0195","S2-0203","S2-0204","S2-0213","S2-0218","S2-0248","S2-0234","S2-0244","S2-0328","S2-0333","S2-0334","S2-0363"))
open("data/appendix_b_ids.txt","w").write("\n".join(sel)+"\n")
B = ["", "# Appendix B. Key evidence rows (selected; all 477 rows are in data/evidence.csv)", "",
     "All rows are **published** numbers. Cycles are copied as published; `sz` = key/signature/share bytes. **Do not compare rows with different core, clock, library, statistic or standard status** (see the comparability_warning column in the CSV; `pre-standard` = round-2/3 Kyber/Dilithium/SPHINCS+, not the final FIPS parameter sets).", "",
     "| id | scheme / parameter / op | device, core, MHz | cycles | stack B | code B | sz B | status |", "|---|---|---|---|---|---|---|---|"]
for i in sel:
    r = R[i]
    impl = md(r["library"])[:44]
    B.append(f"| {i} | {md(r['scheme'])[:22]} {md(r['parameter_set'])[:26]} {md(r['operation'])[:20]} | {md(r['device'])[:22]}, {md(r['core'])[:10]}, {r['clock_mhz']} | {r['cycles']} | {r['stack_bytes']} | {r['flash_or_code_bytes']} | {r['key_or_sig_size_bytes']} | {md(r['standard_status'])} |")
C = ["", "# Appendix C. Sources I could not retrieve (please fetch manually)", "",
     "None of these is used for any number or claim in this report.", "",
     "| Source | Why it matters | Note |", "|---|---|---|",
     "| NSA CNSA 2.0 algorithms advisory and FAQ (media.defense.gov, nsa.gov) | algorithm set, dates, LMS/XMSS firmware-signing guidance | HTTP 403 |",
     "| CISA quantum-readiness pages (cisa.gov/quantum) | US federal migration material | HTTP 403; a NIST-hosted copy of the 2023 fact sheet was used instead |",
     "| UAE National Encryption Policy and executive regulation text; UAE National Cryptography Center algorithm list; Arabic-language sources | UAE requirements for embedded systems | only press copies of the WAM article were read |",
     "| ePrint 2019/844 (pqm4 paper): board and clock | resolves the pqm4 24 MHz / 20 MHz ambiguity | Cloudflare 403 |",
     "| ePrint 2026/1333 (Riou et al., ML-DSA benchmarking pitfalls) | exact reporting recommendations | abstract only |",
     "| ePrint 2022/323 (Dilithium for memory-constrained devices, `m4fstack`), 2025/366 (SLOTHY, M4 to M7), 2020/470 (LMS vs XMSS full paper), 2021/781 (software updates on embedded devices) | stack-optimisation method; M7 numbers; full LMS/XMSS tables | Cloudflare 403 |",
     "| ePrint 2026/312 (RISQrypt), 2026/256 (Adams Bridge), 2026/2343 (KpqC command authentication for unmanned systems) | accelerator and UAV numbers | PDFs 403; abstracts or repository copies only |",
     "| NIST CAVP / CMVP PQC validation lists | which libraries are validated | JavaScript pages not extractable |",
     "| Nordic, ST, NXP, Infineon, Arm product and documentation pages; Bluetooth Core spec; LoRa RP002; IEEE 802.15.4 | exact device specs and PQC accelerator claims | blocked, JavaScript-only or paywalled |",
     "| micro-ROS security documentation; DDS-XRCE specification | micro-ROS security status | guessed paths 404 |",
     "| MCUboot, PX4, ArduPilot GitHub issues and pull requests | whether PQC work is in progress | github.com HTML and API blocked |",
     "| China ICCS; SAMA circular primary; NCA standards; Netherlands TNO handbook; ASD ISM cryptography chapter | other jurisdictions | blocked or 404 |",
     "| Uptane 2.1.0 and later; ISO/SAE 21434; Noise PQ variants | automotive/OTA PQC statements | not retrieved |"]
glos = ROOT / "docs/GLOSSARY.md"
G = []
if glos.exists():
    t = glos.read_text(encoding="utf-8").split("\n")
    G = ["", "# Appendix D. Glossary for a newcomer", ""] + t[1:]
app = "\n".join(A + B + C + G)
body = body.replace("{{APPENDICES}}", app)
(ROOT / "docs/REPORT.md").write_text(body, encoding="utf-8")
left = re.findall(r"\{\{[^}]*\}\}", body)
if left: sys.exit(f"unexpanded macros: {left[:5]}")
print("wrote docs/REPORT.md", len(body.split()), "words")
