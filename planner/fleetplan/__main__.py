"""Command line interface: python -m fleetplan INVENTORY.csv [options].

Author: Huda Mueen
"""

import argparse
import sys
from fractions import Fraction

from . import __version__
from .classify import classify_all
from .loader import LoaderError, load_path
from .report import RENDERERS
from .rules import Parameters


def _fraction(text):
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError(f"not a number: '{text}'") from None


def build_parser():
    p = argparse.ArgumentParser(
        prog="fleetplan",
        description="Fleet migration planner. It supports planning. "
                    "It is not a security guarantee.")
    p.add_argument("inventory", help="inventory CSV file (lines starting with # are comments)")
    p.add_argument("--format", choices=sorted(RENDERERS), default="table",
                   help="output format (default: table)")
    p.add_argument("--explain", action="store_true",
                   help="show every reason and the parameters with their basis")
    p.add_argument("-o", "--output", metavar="OUT", help="write to a file instead of stdout")
    p.add_argument("--version", action="version", version=f"fleetplan {__version__}")
    g = p.add_argument_group("rule parameters (defaults are in docs/PLANNER_RULES.md)")
    g.add_argument("--today-year", type=int, dest="today_year")
    g.add_argument("--sig-horizon-year", type=int, dest="sig_horizon_year")
    g.add_argument("--conf-horizon-year", type=int, dest="conf_horizon_year")
    g.add_argument("--hs-budget-s", type=_fraction, dest="hs_budget_s",
                   help="longest tolerable in band handshake, seconds")
    g.add_argument("--sig-flash-kb", type=_fraction, dest="sig_flash_kb")
    g.add_argument("--sig-ram-kb", type=_fraction, dest="sig_ram_kb")
    g.add_argument("--kem-flash-kb", type=_fraction, dest="kem_flash_kb")
    g.add_argument("--kem-ram-kb", type=_fraction, dest="kem_ram_kb")
    g.add_argument("--hs-bytes", type=_fraction, dest="hs_bytes")
    return p


PARAM_NAMES = ("today_year", "sig_horizon_year", "conf_horizon_year", "hs_budget_s",
               "sig_flash_kb", "sig_ram_kb", "kem_flash_kb", "kem_ram_kb", "hs_bytes")


def main(argv=None, stdout=None, stderr=None):
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        params = Parameters().override(**{n: getattr(args, n) for n in PARAM_NAMES})
        inventory = load_path(args.inventory)
    except (ValueError, LoaderError) as exc:
        print(f"fleetplan: error: {exc}", file=stderr)
        return 2
    results = classify_all(inventory, params)
    text = RENDERERS[args.format](inventory, results, params, args.explain)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
        except OSError as exc:
            print(f"fleetplan: error: cannot write {args.output}: {exc.strerror}", file=stderr)
            return 2
    else:
        stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
