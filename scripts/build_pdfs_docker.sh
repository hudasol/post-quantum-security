#!/usr/bin/env bash
# Build the report and the brief as PDF with the free pandoc/latex Docker image (pandoc 3.6.4 with XeLaTeX),
# for machines without a local pandoc and XeLaTeX. Same pandoc arguments as scripts/build_pdfs.sh; the DejaVu
# fonts are added inside the container from the Alpine package archive. Needs Docker; no account.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/build_report.py
IMAGE=${IMAGE:-pandoc/latex:3.6}
HOSTDIR=$(pwd -W 2>/dev/null || pwd)
MSYS_NO_PATHCONV=1 docker run --rm -v "$HOSTDIR:/data" -w /data --entrypoint sh "$IMAGE" -c '
set -e
apk add --no-cache font-dejavu >/dev/null
for f in REPORT EXECUTIVE_BRIEF; do
  pandoc "docs/$f.md" -o "docs/$f.pdf" --pdf-engine=xelatex --template=scripts/pandoc_template.tex \
    -V mainfont="DejaVu Serif" -V monofont="DejaVu Sans Mono" -V geometry:margin=2.2cm -V fontsize=10pt \
    --resource-path=docs --toc --toc-depth=2 -V author="Huda Mueen" 2>&1 | tail -3
  echo "built docs/$f.pdf"
done'
