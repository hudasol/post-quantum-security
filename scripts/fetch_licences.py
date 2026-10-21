#!/usr/bin/env python3
"""Record the licence of every third party tool, library and package used by the repository.

Three kinds of evidence, one row each in data/third_party_licences.csv (column evidence_kind):
  * github: the licence file of a library at its pinned commit, read from raw.githubusercontent.com
    (rerun with --github; without it the rows of the earlier retrieval are kept with their date);
  * local file: the licence file of a tool fetched or built outside the repository (in the third
    party folder given by THIRD_PARTY, or the work folder given by WORK_DIR, where the Ibex checkout
    and its Python environment live) at the commit or version actually used;
  * package metadata: the licence fields of an installed Python package (importlib.metadata of the
    interpreter that ran it) or of a Debian package (/usr/share/doc/<package>/copyright).
The `licence_as_read` column is a keyword match on the file, or the metadata field as written; it is
not legal advice. A component whose file or metadata cannot be read is written as "not retrieved".
Paths are written relative to $THIRD_PARTY and $WORK_DIR. Usage:
  THIRD_PARTY=<folder> WORK_DIR=<folder> python3 scripts/fetch_licences.py [--github]

Also writes docs/LICENSES.md from the CSV, so the document and the data cannot disagree.
"""
import csv
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "third_party_licences.csv"
DOC = ROOT / "docs" / "LICENSES.md"
TP = Path(os.environ.get("THIRD_PARTY", "THIRD_PARTY_not_set"))
WORK = Path(os.environ.get("WORK_DIR", "WORK_DIR_not_set"))


def shown(p):
    """Path as written to the CSV: relative to $THIRD_PARTY or $WORK_DIR, never a local machine path."""
    t = str(p)
    for base, name in ((str(TP), "$THIRD_PARTY"), (str(WORK), "$WORK_DIR")):
        if t.startswith(base):
            return name + t[len(base):]
    return t
FIELDS = ["component", "role", "evidence_kind", "repo", "pinned_commit", "licence_file", "licence_file_url",
          "licence_as_read", "file_sha256_16", "committed_to_this_repository", "retrieved"]

LIBS = [
    ("mlkem-native", "pq-code-package/mlkem-native", "d1b2fe782888bdb761a50336012923180be7f502", "E1 ML-KEM benchmark; WP7 RTL simulated cycles"),
    ("mldsa-native", "pq-code-package/mldsa-native", "834a90d5e846ffa1e1611bd24e160bb2e9b86d35", "E1 ML-DSA benchmark; WP7 RTL simulated cycles"),
    ("wolfSSL", "wolfSSL/wolfssl", "3c5eead44904df64e6a5a1f4ebdce377d35a849a", "E2 hash based signature verification"),
    ("wolfBoot", "wolfSSL/wolfBoot", "eb710fe1656f20addb736b5c205f18bf53fa2998", "E4 boot time"),
    ("TF-PSA-Crypto", "Mbed-TLS/TF-PSA-Crypto", "73c5da561c8e5253db7b1fb440eda86fde8d8024", "E2 comparison"),
    ("pqm4", "mupq/pqm4", "5e5cc76d0b072ee7077e58afcbc619a1a67a53b4", "reference rows only"),
    ("slhdsa-c", "pq-code-package/slhdsa-c", "174c02e42257f95c210963272877c49dbb50070f", "SLH-DSA cross check"),
    ("liboqs", "open-quantum-safe/liboqs", "5a1a854b0dc9f2141bdc771c555ee60c37950183", "host measurements"),
]
# (component, role, directory holding the licence file, licence file name, version when not a git checkout)
LOCAL = [
    ("Ibex (lowRISC)", "WP7 RTL simulated cycles (rtlsim, simulated with Verilator, not copied)", WORK / "ibex", "LICENSE", ""),
    ("OpenHW Group CV32E40P", "WP7 RTL simulated cycles (fetched by rtlsim/fetch_cv32e40p.sh, simulated, not copied)", TP / "wp7_work/rtl/cv32e40p", "LICENSE", ""),
    ("VexRiscv", "WP7, prepared but not built (dependency download refused)", TP / "wp7_work/rtl/vex/VexRiscv", "LICENSE", ""),
    ("sbt", "WP7 VexRiscv build tool, prepared but not used", TP / "wp7_work/rtl/vex/sbt", "LICENSE", "1.10.9 (archive sbt-1.10.9.tgz)"),
    ("ProVerif", "WP4 formal verification of the session and update design (built outside the repository by formal/install.sh)", TP / "proverif/proverif2.05", "LICENSE", "2.05 (tarball SHA-256 in formal/proverif.sha256)"),
    ("ns-3", "WP3 network simulation (fetched and built outside the repository by netsim/fetch_build.sh)", TP / "ns-3-dev", "LICENSE", ""),
    ("signetlabdei lorawan module", "WP3 LoRaWAN simulation (fetched by netsim/fetch_build.sh)", TP / "ns-3-dev/src/lorawan", "LICENSE", ""),
    ("PX4-Autopilot", "WP1 firmware builds for memory use; WP2 software in the loop (fetched by flightstack/fetch.sh)", TP / "PX4-Autopilot", "LICENSE", ""),
    ("ArduPilot", "WP1 firmware builds for memory use; WP2 software in the loop (fetched by flightstack/fetch.sh); only section headers, the linker MEMORY block and board definition values are kept as data", TP / "ardupilot", "COPYING.txt", ""),
    ("CrashDebug", "ArduPilot H7 build dependency, build time only", TP / "ardupilot/modules/CrashDebug", "LICENSE", ""),
    ("ARM CMSIS core", "WP7 board images and cache register citations (fetched at build time)", TP / "wp7_work/board_kit_libs/cmsis_core", "LICENSE.md", ""),
    ("ST cmsis_device_l5", "WP7 NUCLEO-L552ZE-Q images (fetched at build time)", TP / "wp7_work/board_kit_libs/cmsis_device_l5", "LICENSE.md", ""),
    ("ST cmsis_device_l4", "WP7 board images (fetched at build time)", TP / "wp7_work/board_kit_libs/cmsis_device_l4", "LICENSE.md", ""),
    ("Renode", "WP7 emulator check of the cache register writes (fetched by bench/board_kit/fetch_renode.sh)", TP / "renode/renode_1.16.1-dotnet_portable/licenses", "renode-license", "1.16.1"),
]
DEBIAN = [
    ("verilator", "Verilator", "WP7 RTL simulation of Ibex and CV32E40P"),
    ("gcc-riscv64-unknown-elf", "RISC-V GCC toolchain", "WP7 compiler for the RTL simulated benchmarks"),
    ("binutils-riscv64-unknown-elf", "RISC-V binutils", "WP7 assembler and linker for the RTL simulated benchmarks"),
    ("picolibc-riscv64-unknown-elf", "picolibc", "WP7 C library linked into the RTL simulated benchmarks"),
]
# Python packages: requirements.txt is read; these are added with the interpreter that ran them.
EXTRA_PY = [("fusesoc", WORK / "ibexvenv/bin/python", "WP7 Ibex build configuration"),
            ("pymavlink", TP / "venv_wp2/bin/python", "MAVLink payload lengths (mission/measure_payloads.py)")]
PATTERNS = [("Apache-2.0", r"Apache License,?\s+Version 2\.0"), ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
            ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"), ("LGPL-3.0", r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3"),
            ("MIT", r"Permission is hereby granted, free of charge"),
            ("ISC", r"Permission to use, copy, modify, and/or distribute this software for any purpose"),
            ("BSD-3-Clause", r"Redistribution and use in source and binary forms.{0,1500}Neither the name"),
            ("Solderpad Hardware License 0.51", r"SOLDERPAD HARDWARE LICENSE\s+version 0\.51"),
            ("CC0", r"CC0 1\.0|Creative Commons Zero"),
            ("GPL-3.0 or later (licence notice)", r"GNU General Public License as published by\s+the Free Software Foundation;?\s+either version 3")]
NAMES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "LICENSE-APACHE", "LICENSE-MIT"]


def match(text):
    ids = [k for k, p in PATTERNS if re.search(p, text, re.I | re.S)]
    return "; ".join(ids) or "unrecognised"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def today():
    return datetime.date.today().isoformat()


def github_rows():
    rows = []
    for name, repo, commit, role in LIBS:
        found = []
        for n in NAMES:
            url = f"https://raw.githubusercontent.com/{repo}/{commit}/{n}"
            try:
                with urllib.request.urlopen(url, timeout=60) as r:
                    t = r.read().decode("utf-8", "replace")
            except Exception:
                continue
            found.append((n, url, match(t), sha(t)))
        if not found:
            found = [("(none found at root)", "", "not retrieved", "")]
        for n, url, ids, h in found:
            rows.append(dict(component=name, role=role, evidence_kind="github", repo=f"https://github.com/{repo}", pinned_commit=commit,
                             licence_file=n, licence_file_url=url, licence_as_read=ids, file_sha256_16=h,
                             committed_to_this_repository="no (cloned or downloaded at run time)", retrieved=today()))
    return rows


def kept_github_rows():
    """Rows of the earlier GitHub retrieval, kept with their retrieval date (rerun with --github to refetch)."""
    if not OUT.exists():
        return github_rows()
    with open(OUT, newline="", encoding="utf-8") as fh:
        old = [r for r in csv.DictReader(fh) if r.get("evidence_kind", "github") == "github"]
    names = {n for n, *_ in LIBS}
    out = []
    for r in old:
        if r["component"] not in names:
            continue
        r = {k: r.get(k, "") for k in FIELDS}
        r["evidence_kind"] = "github"
        role = {n: ro for n, _, _, ro in LIBS}[r["component"]]
        r["role"] = role
        out.append(r)
    return out


def git(path, *args):
    r = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def local_rows():
    rows = []
    for name, role, d, fname, version in LOCAL:
        p = d / fname
        top = git(d, "rev-parse", "--show-toplevel")
        commit = git(d, "rev-parse", "HEAD") if top else ""
        desc = git(d, "describe", "--tags", "--always") if top else ""
        url = git(d, "remote", "get-url", "origin") if top else ""
        pin = version or (f"{commit} ({desc})" if commit else "not recorded")
        if p.exists():
            t = p.read_text(encoding="utf-8", errors="replace")
            ids, h = match(t), sha(t)
        else:
            ids, h = "not retrieved", ""
        rows.append(dict(component=name, role=role, evidence_kind="local file", repo=url, pinned_commit=pin, licence_file=fname,
                         licence_file_url=f"local copy outside the repository: {shown(p)}", licence_as_read=ids, file_sha256_16=h,
                         committed_to_this_repository="no (fetched or built outside the repository)", retrieved=today()))
    return rows


def debian_rows():
    rows = []
    for pkg, name, role in DEBIAN:
        v = subprocess.run(["dpkg-query", "-W", "-f=${Version}", pkg], capture_output=True, text=True)
        p = Path("/usr/share/doc") / pkg / "copyright"
        if v.returncode == 0 and p.exists():
            t = p.read_text(encoding="utf-8", errors="replace")
            lic = sorted({re.sub(r"^(BSD\d|Other|Default|FreeBSD|UCB|AGPL3|GPL2)-\d+$", r"\1", m.strip()) for m in re.findall(r"^License:\s*(.+)$", t, re.M)})
            ids, h = ("; ".join(lic) if lic else match(t)), sha(t)
        else:
            ids, h = "not retrieved", ""
        rows.append(dict(component=name, role=role, evidence_kind="package metadata (Debian copyright file)", repo=f"Debian package {pkg}",
                         pinned_commit=v.stdout.strip() or "not installed", licence_file=str(p), licence_file_url="",
                         licence_as_read=ids, file_sha256_16=h, committed_to_this_repository="no (system package)", retrieved=today()))
    return rows


META = r"""
import json, sys
from importlib import metadata
out = {}
for n in sys.argv[1:]:
    try:
        m = metadata.metadata(n)
    except metadata.PackageNotFoundError:
        out[n] = None
        continue
    cls = [c.split('::')[-1].strip() for c in (m.get_all('Classifier') or []) if c.startswith('License ::')]
    lic = (m.get('License') or '').strip()
    if len(lic) > 40 or 'opyright' in lic or 'agreement' in lic.lower():
        lic = str()
    lic = (m.get('License-Expression') or '').strip() or lic
    out[n] = {'version': m.get('Version'), 'licence': lic, 'classifiers': cls}
print(json.dumps(out))
"""


def py_meta(python, names):
    r = subprocess.run([str(python), "-c", META, *names], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {n: None for n in names}


def python_rows():
    req = [l.split("==") for l in (ROOT / "requirements.txt").read_text().splitlines() if "==" in l and not l.startswith("#")]
    rows = []
    got = py_meta(sys.executable, [n for n, _ in req])
    todo = [(n, v, sys.executable, "Python package of requirements.txt (scripts, tests and models)", got.get(n)) for n, v in req]
    for n, py, role in EXTRA_PY:
        m = py_meta(py, [n]).get(n) if Path(py).exists() else None
        todo.append((n, (m or {}).get("version", ""), py, role, m))
    for n, pinned, py, role, m in todo:
        if m is None:
            lic, ver = "not retrieved (package not installed for this interpreter)", pinned
        else:
            parts = [m["licence"]] if m["licence"] else []
            parts += [c for c in m["classifiers"] if c not in parts]
            lic, ver = ("; ".join(parts) or "not stated in the package metadata"), m["version"]
            if pinned and ver != pinned:
                ver = f"{ver} installed (requirements.txt pins {pinned})"
        rows.append(dict(component=n, role=role, evidence_kind="package metadata (Python importlib.metadata)", repo=f"PyPI package {n}",
                         pinned_commit=ver, licence_file="package METADATA (License-Expression, License, classifiers)",
                         licence_file_url=f"interpreter {shown(py)}", licence_as_read=lic, file_sha256_16="",
                         committed_to_this_repository="no (installed package)", retrieved=today()))
    return rows


NOTES = """Notes:

- mlkem native, mldsa native and slhdsa-c carry a combined licence statement (Apache-2.0, MIT or ISC, as read). TF-PSA-Crypto offers Apache-2.0 or GPL-2.0 as read.
- wolfSSL and wolfBoot are GPL-3.0 as read. They are downloaded by `bench/mcu/fetch_libs.sh e2` for local experiments only. Do not redistribute builds without checking the licence.
- pqm4 has no licence file at the repository root at the pinned commit. Its licences are set per implementation directory. It is used only to read published benchmark rows and to read configuration files, never copied.
- liboqs is MIT as read (LICENSE.txt). Host measurements in `bench/host/` are labelled host measured.
- Tools that run outside the repository (simulators, compilers, flight stacks, the protocol verifier) are recorded with the licence file of the copy that was used; none of their code is stored in this repository.
- A Debian copyright file lists the licence of each part of the package; all licence names it gives are listed.
"""


def write_doc(rows):
    retrieved = sorted({r["retrieved"] for r in rows if r["retrieved"]})
    L = ["# Third party licences", "",
         "Author: Huda Mueen. Generated by `scripts/fetch_licences.py` from `data/third_party_licences.csv`; do not edit by hand. "
         "Every row comes from a licence file read at the pinned commit or version (on raw.githubusercontent.com or in the local copy that was used), "
         "or from package metadata (Python importlib.metadata or a Debian copyright file). "
         f"Retrieval dates: {', '.join(retrieved)}. The 'as read' column is a keyword match or the metadata field as written, not legal advice. "
         "No third party code is stored in this repository.", "",
         "| Component | Used for | Evidence | Pinned commit or version | Licence file | Licence as read |", "|---|---|---|---|---|---|"]
    for r in rows:
        pin = r["pinned_commit"]
        pin = f"`{pin[:12]}`" if re.fullmatch(r"[0-9a-f]{40}", pin) else pin
        L.append("| " + " | ".join(str(x).replace("|", "/") for x in (r["component"], r["role"], r["evidence_kind"], pin,
                                                                      r["licence_file"], r["licence_as_read"])) + " |")
    L += ["", NOTES, "## Datasets and documents used as sources", "",
          "Every row of `data/evidence.csv` cites a source URL. The repository stores extracted numbers and short paraphrases, not the papers, "
          "slides or web pages. NIST publications (FIPS 203, 204, 205, SP 800-208) and IETF RFCs are cited for sizes and statements only. "
          "I have not verified the reuse terms of each paper; the numbers are factual values with attribution, and anything longer than a short "
          "phrase is paraphrased. If a rights holder objects to a row, remove it.", "",
          "## Licence of this repository", "",
          "All rights reserved by Huda Mueen. Permission is needed before use, copying, modification, distribution or sale; see `LICENSE` and "
          "`docs/LICENCE_DECISION.md`. The licences in the table above belong to third party components and are not changed by this.", ""]
    DOC.write_text("\n".join(L), encoding="utf-8")


def main():
    rows = (github_rows() if "--github" in sys.argv else kept_github_rows()) + local_rows() + debian_rows() + python_rows()
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    write_doc(rows)
    for r in rows:
        print(r["component"], "|", r["pinned_commit"][:40], "|", r["licence_as_read"])


if __name__ == "__main__":
    main()
