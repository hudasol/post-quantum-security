#!/usr/bin/env bash
# Build the Ibex simple system Verilator model following the Ibex README
# (examples/simple_system/README.md at the pinned commit), with the named
# "small" configuration from ibex_configs.yaml.
# Requires: verilator, libelf-dev, python3 venv. Author: Huda Mueen.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/config.sh"

VENV="$WORK_DIR/ibexvenv"
if [ ! -x "$VENV/bin/fusesoc" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q "fusesoc==$FUSESOC_VERSION" pyyaml mako packaging
fi

cd "$WORK_DIR/ibex"
OPTS="$("$VENV/bin/python" util/ibex_config.py "$IBEX_CONFIG" fusesoc_opts)"
echo "fusesoc options: $OPTS"
PATH="$VENV/bin:$PATH" fusesoc --cores-root=. run --target=sim --setup --build \
  lowrisc:ibex:ibex_simple_system $OPTS
ls -l build/lowrisc_ibex_ibex_simple_system_0/sim-verilator/Vibex_simple_system
