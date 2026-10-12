"""Shared fixtures for the planner tests.

Author: Huda Mueen
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fleetplan.classify import classify, classify_all  # noqa: E402
from fleetplan.loader import parse_text  # noqa: E402
from fleetplan.rules import Parameters  # noqa: E402

COLUMNS = ["device_id", "ram_kb", "flash_kb", "bootrom_verifier_updatable",
           "link_bandwidth_bps", "service_life_remaining_years", "data_lifetime_years",
           "free_flash_kb", "free_ram_kb", "updatable_bootloader_stage", "core", "notes"]

# A device that is exposed on neither side, with ample headroom.
BASE = {
    "device_id": "T1", "ram_kb": "256", "flash_kb": "1024",
    "bootrom_verifier_updatable": "yes", "link_bandwidth_bps": "57600",
    "service_life_remaining_years": "1", "data_lifetime_years": "1",
    "free_flash_kb": "500", "free_ram_kb": "100", "updatable_bootloader_stage": "yes",
    "core": "", "notes": "",
}


def csv_text(*rows, comments=()):
    lines = list(comments) + [",".join(COLUMNS)]
    for row in rows:
        merged = dict(BASE)
        merged.update(row)
        lines.append(",".join(merged[c] for c in COLUMNS))
    return "\n".join(lines) + "\n"


def one(params=None, **overrides):
    """Classify a single device built from BASE plus overrides."""
    inv = parse_text(csv_text(overrides))
    return classify(inv.records[0], params)


SIG = {"service_life_remaining_years": "10"}   # 10 > 4: signature exposed
CONF = {"data_lifetime_years": "20"}           # 20 > 9: confidentiality exposed
