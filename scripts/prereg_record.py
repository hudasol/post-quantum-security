#!/usr/bin/env python3
"""Record of the preregistered predictions that does not depend on commit IDs.

On 2026-10-29 the author fields of early commits and some commit message trailers were corrected. Rewriting a
commit's metadata gives it a new ID, and every later commit gets a new ID as well, although no file, tree, parent
order or date changed. Commit IDs quoted in earlier documents (for example `9cc1744` in docs/PREDICTIONS_V6.md)
therefore no longer resolve on the remote. This script writes three files so that a reader can verify the
predictions without old commit IDs:

  data/history/prereg_hashes.csv      every hashed prediction file: its SHA-256 now, the SHA-256 stored in its
                                      hash file, whether they match, and the commit (current ID) that first added
                                      the prediction file and the hash file
  data/history/snapshots.csv          files of earlier repository states that scoring scripts read, with the
                                      commit (current ID) they come from and their SHA-256; small files are kept
                                      as copies in data/history/snapshots/
  docs/PREREGISTRATION_RECORD.md      the same in prose, with the note on the corrected history

data/history/commit_ids_2026-10-29.csv maps every earlier commit ID to its current ID and gives the tree ID,
which is the same for both (checked when the map was written). Scripts that need an earlier state call
`snapshot_text(name)`, which reads the committed copy or, for large files, the recorded commit, and fails if the
SHA-256 differs from the record. Author: Huda Mueen.

Usage: python3 scripts/prereg_record.py [--write-snapshots]   (--write-snapshots copies the small files once)
"""
import csv
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "history"
SNAP_DIR = HIST / "snapshots"
MAP = HIST / "commit_ids_2026-10-29.csv"
REWRITE_DATE = "2026-10-29"

# Files of earlier states read by scoring and summary scripts: name, commit (current ID), path at that commit,
# whether a copy is committed (False for large files, which are read from the commit and checked by hash), and
# the scripts that read it.
SNAPSHOTS = [
    ("qemu_first_round_stack", "fb3c121", "bench/mcu/qemu_results/stack.csv", True,
     "bench/mcu/analyze_qemu.py, scripts/score_predictions_v2.py"),
    ("qemu_first_round_image_size", "fb3c121", "bench/mcu/qemu_results/image_size.csv", True,
     "bench/mcu/analyze_qemu.py, scripts/score_predictions_v2.py"),
    ("evidence_at_v3_predictions", "e0fd150", "data/evidence.csv", False,
     "scripts/score_predictions_v3.py, scripts/summarize_verification3.py"),
]


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def full_id(short):
    return git("rev-parse", short + "^{commit}").decode().strip()


def read_snapshots():
    with open(HIST / "snapshots.csv", newline="", encoding="utf-8") as fh:
        return {r["name"]: r for r in csv.DictReader(fh)}


def commit_of(name):
    """Short current ID of the commit a recorded snapshot comes from."""
    return read_snapshots()[name]["commit"][:7]


def snapshot_text(name):
    """Text of a recorded file of an earlier state, checked against its recorded SHA-256."""
    r = read_snapshots()[name]
    if r["copy"]:
        data = (ROOT / r["copy"]).read_bytes()
    else:
        data = git("show", f"{r['commit']}:{r['path']}")
    if sha256(data) != r["sha256"]:
        raise ValueError(f"{name}: SHA-256 differs from data/history/snapshots.csv")
    return data.decode("utf-8")


def hash_files():
    """(prediction file, stored hash, hash file) for every line of every docs/*.sha256 file."""
    out = []
    for hf in sorted((ROOT / "docs").glob("*.sha256")):
        for line in hf.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2 and len(parts[0]) == 64:
                out.append((parts[1].lstrip("*"), parts[0], hf.relative_to(ROOT).as_posix()))
    return out


def first_commit(path):
    ids = git("log", "--diff-filter=A", "--format=%H %ad", "--date=short", "--", path).decode().split("\n")
    ids = [x for x in ids if x.strip()]
    return ids[-1].split() if ids else ["", ""]


def old_ids():
    with open(MAP, newline="", encoding="utf-8") as fh:
        return {r["new_id"]: r["old_id"] for r in csv.DictReader(fh)}


def main(argv):
    rev = old_ids()
    rows = []
    for path, stored, hf in hash_files():
        data = (ROOT / path).read_bytes()
        now = sha256(data)
        norm = sha256(data.replace(b"\r\n", b"\n"))
        match = "yes" if stored in (now, norm) else "no"
        c, d = first_commit(path)
        ch, dh = first_commit(hf)
        first = git("show", f"{c}:{path}")
        first_match = "yes" if stored in (sha256(first), sha256(first.replace(b"\r\n", b"\n"))) else "no"
        rows.append(dict(file=path, sha256_now=now, hash_file=hf, sha256_stored=stored, match_now=match,
                         match_at_first_commit=first_match,
                         first_commit=c, first_commit_date=d, first_commit_before_2026_10_29=rev.get(c, ""),
                         hash_file_commit=ch, hash_file_commit_date=dh))
    HIST.mkdir(parents=True, exist_ok=True)
    with open(HIST / "prereg_hashes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    snaps = []
    for name, short, path, copy, readers in SNAPSHOTS:
        cid = full_id(short)
        data = git("show", f"{cid}:{path}")
        rel = ""
        if copy:
            dest = SNAP_DIR / name / Path(path).name
            rel = dest.relative_to(ROOT).as_posix()
            if "--write-snapshots" in argv:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
            if sha256(dest.read_bytes()) != sha256(data):
                raise SystemExit(f"{rel} differs from {path} at {cid}")
        snaps.append(dict(name=name, commit=cid, commit_before_2026_10_29=rev.get(cid, ""), path=path,
                          copy=rel, bytes=len(data), sha256=sha256(data), read_by=readers))
    with open(HIST / "snapshots.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(snaps[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(snaps)
    with open(MAP, newline="", encoding="utf-8") as fh:
        n_map = sum(1 for _ in csv.DictReader(fh))
    L = ["# Preregistration record", "",
         "Author: Huda Mueen. Generated by `scripts/prereg_record.py`; do not edit by hand.", "",
         "## Why this file exists", "",
         f"On {REWRITE_DATE} the author fields of early commits and some commit message trailers were corrected. "
         "Changing the metadata of a commit gives it a new ID, and every later commit then gets a new ID as well. "
         "No file, tree, parent order or date changed: for each of the "
         f"{n_map} commits the tree ID before and after is the same "
         "(`data/history/commit_ids_2026-10-29.csv` lists the earlier ID, the current ID and the tree ID of each). "
         "Commit IDs quoted in documents written before that date refer to the earlier IDs; the map translates "
         "them. The history was not rewritten again afterwards.", "",
         "A prediction file is verified by its SHA-256, not by a commit ID: compute the SHA-256 of the file and "
         "compare it with the hash file committed with it. The table below does this for every hashed prediction "
         "file and names the commit, by its current ID, that first added each one.", "",
         "## Hashed prediction files", "",
         "| file | SHA-256 now (first 16) | stored in | matches now | matches as first added | first added (current ID) "
         "| date | earlier ID |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| `{r['file']}` | {r['sha256_now'][:16]} | `{r['hash_file']}` | {r['match_now']} | "
                 f"{r['match_at_first_commit']} | "
                 f"{r['first_commit'][:7]} | {r['first_commit_date']} | {r['first_commit_before_2026_10_29'][:7]} |")
    changed = [r["file"] for r in rows if r["match_now"] != "yes" and r["match_at_first_commit"] == "yes"]
    L += ["", "Full hashes: `data/history/prereg_hashes.csv`. `docs/PREDICTIONS_V3.md` is hashed after line "
          "endings are normalised to a line feed, as its scoring script does. "
          + (("Files that match their stored hash as first added but not now were scored in place later; the "
              "version that was hashed is the one in the commit named in the table: "
              + ", ".join(f"`{f}`" for f in changed) + ".") if changed else ""), "",
          "## Earlier repository states read by scripts", "",
          "Scripts that read a file as it stood in an earlier commit now read it through `snapshot_text` in "
          "`scripts/prereg_record.py`: small files from a committed copy, large files from the recorded commit, "
          "and in both cases the SHA-256 is checked against `data/history/snapshots.csv`. The commit IDs live in "
          "that one file instead of in each script.", "",
          "| name | path | commit (current ID) | earlier ID | bytes | copy | read by |", "|---|---|---|---|---|---|---|"]
    for s in snaps:
        L.append(f"| {s['name']} | `{s['path']}` | {s['commit'][:7]} | {s['commit_before_2026_10_29'][:7]} | "
                 f"{s['bytes']} | {'`' + s['copy'] + '`' if s['copy'] else 'none, read from the commit'} | "
                 f"{s['read_by']} |")
    L.append("")
    (ROOT / "docs" / "PREREGISTRATION_RECORD.md").write_text("\n".join(L), encoding="utf-8")
    bad = [r["file"] for r in rows if r["match_at_first_commit"] != "yes"]
    print(f"{len(rows)} hashed files, {len(bad)} mismatches; {len(snaps)} snapshots")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
