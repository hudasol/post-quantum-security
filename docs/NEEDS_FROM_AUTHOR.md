# What only the author can supply

Author: Huda Mueen. Opened 2026-10-16. Items are in order of value to the study. Nothing here was worked around.

| # | Item | Why it is needed | Blocks |
|---|---|---|---|
| 1 | A few hours with a borrowed STM32 Cortex-M4F board (NUCLEO-L4R5ZI or STM32F4 Discovery), its USB cable and lab permission to flash it | the only route to real cycle counts; the session plan is `docs/BOARD_RUN_PROTOCOL.md` | experiments B0 and B1; any claim about cycles on this firmware |
| 2 | A decision on the author field of the earlier commits | the 121 commits made before 2026-10-16 carry an author name and address that are not the author's own; changing them needs a history rewrite and a force push, which this run is not allowed to do | nothing technical; it concerns attribution in the public history |
| 3 | A representative flight controller profile (core, clock, RAM and flash budget left after the flight stack, link type) from a supervisor or partner | the planner and the link study use invented fleets and generic links; one real profile would replace an assumption with a fact | turning the synthetic planner study into a case study |
| 4 | The NSA CNSA 2.0 algorithms advisory (separate from the FAQ) or CNSSP 15 as a PDF | per category transition dates (firmware signing, networking equipment, custom systems) are not in the FAQ | dated statements by equipment type |
| 5 | Resolved 2026-10-18: no longer needed | the PDFs are rebuilt with `scripts/build_pdfs_docker.sh`, which uses the free `pandoc/latex:3.1` Docker image (Docker Desktop is already installed here); a local pandoc 3.1 and XeLaTeX with DejaVu fonts also work with `scripts/build_pdfs.sh` | nothing |
| 6 | Supervision for the proposal (`docs/PROPOSAL_ATRC.md`) | a named supervisor is part of the ask | submission of the proposal |
