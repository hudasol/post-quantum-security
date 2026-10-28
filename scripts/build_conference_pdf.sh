#!/usr/bin/env bash
# Compile the conference paper (IEEE conference format) and its anonymised copy with pdflatex and bibtex.
# Needs TeX Live with the IEEEtran class (Debian package texlive-publishers). Run scripts/build_paper.py first.
set -euo pipefail
cd "$(dirname "$0")/../docs/conference"
for f in paper paper_anon; do
  rm -f "$f.aux" "$f.bbl" "$f.blg" "$f.log" "$f.out"
  pdflatex -interaction=nonstopmode -halt-on-error "$f.tex" >/dev/null
  bibtex "$f" >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error "$f.tex" >/dev/null
  pdflatex -interaction=nonstopmode -halt-on-error "$f.tex" >/dev/null
  grep -E "Warning: (Citation|Reference)" "$f.log" || true
  rm -f "$f.aux" "$f.blg" "$f.log" "$f.out" "$f.bbl"
done
pdfinfo paper.pdf | grep Pages
