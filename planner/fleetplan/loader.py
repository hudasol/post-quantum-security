"""Strict inventory loader.

Author: Huda Mueen

Structural problems (missing required column, duplicate or blank device_id,
wrong field count, unreadable file) raise LoaderError with the line number.
A bad value in a single cell does not stop the run. It is recorded on the
field, and the classifier then reports UNKNOWN for that device. The loader
never repairs or guesses a value.
"""

import csv
import re
from dataclasses import dataclass, field
from fractions import Fraction

REQUIRED_COLUMNS = (
    "device_id", "ram_kb", "flash_kb", "bootrom_verifier_updatable",
    "link_bandwidth_bps", "service_life_remaining_years", "data_lifetime_years",
)
OPTIONAL_COLUMNS = (
    "free_flash_kb", "free_ram_kb", "updatable_bootloader_stage", "core", "notes",
)

NUMERIC_NONNEGATIVE = (
    "ram_kb", "flash_kb", "service_life_remaining_years", "data_lifetime_years",
    "free_flash_kb", "free_ram_kb",
)
NUMERIC_POSITIVE = ("link_bandwidth_bps",)
YES_NO = ("bootrom_verifier_updatable", "updatable_bootloader_stage")

_NUMBER = re.compile(r"^[0-9]+(\.[0-9]+)?$")
_NEGATIVE = re.compile(r"^-[0-9]+(\.[0-9]+)?$")


class LoaderError(ValueError):
    """The inventory cannot be read as a table of devices."""


@dataclass(frozen=True)
class Field:
    name: str
    status: str  # "ok", "missing" or "invalid"
    value: object = None
    raw: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Record:
    device_id: str
    line: int
    fields: dict


@dataclass
class Inventory:
    source: str
    records: list
    synthetic: bool
    comments: list = field(default_factory=list)
    ignored_columns: list = field(default_factory=list)


def _parse_number(name, raw, positive):
    s = raw.strip()
    if s == "" or s.lower() == "unknown":
        return Field(name, "missing", None, raw, "blank or unknown")
    if _NEGATIVE.match(s):
        return Field(name, "invalid", None, raw, f"negative value '{s}'")
    if not _NUMBER.match(s):
        return Field(name, "invalid", None, raw, f"not a number '{s}'")
    value = Fraction(s)
    if positive and value <= 0:
        return Field(name, "invalid", None, raw, f"must be greater than 0, got '{s}'")
    return Field(name, "ok", value, raw)


def _parse_yes_no(name, raw):
    s = raw.strip().lower()
    if s == "" or s == "unknown":
        return Field(name, "missing", None, raw, "blank or unknown")
    if s == "yes":
        return Field(name, "ok", True, raw)
    if s == "no":
        return Field(name, "ok", False, raw)
    return Field(name, "invalid", None, raw, f"expected yes or no, got '{raw.strip()}'")


def _parse_cell(name, raw):
    if name in NUMERIC_POSITIVE:
        return _parse_number(name, raw, True)
    if name in NUMERIC_NONNEGATIVE:
        return _parse_number(name, raw, False)
    if name in YES_NO:
        return _parse_yes_no(name, raw)
    text = raw.strip()
    return Field(name, "ok" if text else "missing", text, raw, "" if text else "blank")


def parse_text(text, source="<text>"):
    """Parse inventory text and return an Inventory."""
    comments = []
    rows = []  # (line number, text)
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("#"):
            comments.append(line)
        elif line.strip():
            rows.append((number, line))
    if not rows:
        raise LoaderError(f"{source}: no header line found")

    header_line, header_text = rows[0]
    header = [h.strip() for h in next(csv.reader([header_text]))]
    seen = set()
    for h in header:
        if h in seen:
            raise LoaderError(f"{source}, line {header_line}: duplicate column '{h}'")
        seen.add(h)
    absent = [c for c in REQUIRED_COLUMNS if c not in seen]
    if absent:
        raise LoaderError(
            f"{source}, line {header_line}: required column(s) missing from header: "
            + ", ".join(absent))
    known = set(REQUIRED_COLUMNS) | set(OPTIONAL_COLUMNS)
    ignored = [h for h in header if h not in known]

    records = []
    ids = {}
    synthetic = any("synthetic" in c.lower() for c in comments)
    for number, line in rows[1:]:
        cells = next(csv.reader([line]))
        if len(cells) != len(header):
            raise LoaderError(
                f"{source}, line {number}: expected {len(header)} fields, found {len(cells)}")
        raw = dict(zip(header, cells))
        device_id = raw["device_id"].strip()
        if not device_id:
            raise LoaderError(f"{source}, line {number}: device_id is blank")
        if device_id in ids:
            raise LoaderError(
                f"{source}, line {number}: duplicate device_id '{device_id}' "
                f"(first seen on line {ids[device_id]})")
        ids[device_id] = number
        if "synthetic" in raw.get("notes", "").lower():
            synthetic = True
        parsed = {"device_id": Field("device_id", "ok", device_id, raw["device_id"])}
        for name in REQUIRED_COLUMNS[1:] + OPTIONAL_COLUMNS:
            parsed[name] = _parse_cell(name, raw.get(name, ""))
        for free, total in (("free_flash_kb", "flash_kb"), ("free_ram_kb", "ram_kb")):
            f, t = parsed[free], parsed[total]
            if f.status == "ok" and t.status == "ok" and f.value > t.value:
                parsed[free] = Field(
                    free, "invalid", None, f.raw,
                    f"{free} '{f.raw.strip()}' exceeds {total} '{t.raw.strip()}'")
        records.append(Record(device_id, number, parsed))
    return Inventory(source, records, synthetic, comments, ignored)


def load_path(path):
    """Read an inventory file (UTF 8) and return an Inventory."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        raise LoaderError(f"cannot read {path}: {exc.strerror or exc}") from None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LoaderError(f"{path}: not valid UTF 8 text ({exc.reason})") from None
    return parse_text(text, str(path))
