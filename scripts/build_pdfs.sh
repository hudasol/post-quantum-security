#!/usr/bin/env bash
# Build the report, the brief and the paper as PDF from the generated markdown.
# Needs pandoc 3.1 and xelatex; fonts DejaVu Serif and DejaVu Sans Mono. Without them, use scripts/build_pdfs_docker.sh. The template is pandoc's default LaTeX template without lmodern.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/build_report.py
for f in REPORT EXECUTIVE_BRIEF PAPER; do
  pandoc "docs/$f.md" -o "docs/$f.pdf" --pdf-engine=xelatex --template=scripts/pandoc_template.tex \
    -V mainfont="DejaVu Serif" -V monofont="DejaVu Sans Mono" -V geometry:margin=2.2cm -V fontsize=10pt \
    --resource-path=docs --lua-filter=scripts/cite_keys.lua --toc --toc-depth=2 -V author="Huda Mueen" -M author="Huda Mueen" 2>&1 | tail -3
done
