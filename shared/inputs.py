"""Loader for data/shared_inputs.csv: one parameter, one value, one source.

Author: Huda Mueen.

Every parameter that two or more studies use is defined once in data/shared_inputs.csv. The studies read
it through this module; their own input files keep only the parameters that one study uses.
Nothing cryptographic is implemented here.
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "shared_inputs.csv")
FIELDS = ["parameter", "value", "unit", "source", "label", "used_by", "note"]
STUDIES = {"energy", "bootchain", "mission", "linksim", "stats"}

_CACHE = {}


def rows(path=PATH):
    """Return the rows of the shared file as a list of dicts (cached per path)."""
    if path not in _CACHE:
        with open(path, newline="", encoding="utf-8") as fh:
            rd = csv.DictReader(fh)
            if rd.fieldnames != FIELDS:
                raise ValueError("unexpected columns in %s: %s" % (path, rd.fieldnames))
            _CACHE[path] = list(rd)
    return [dict(r) for r in _CACHE[path]]


def values(path=PATH):
    """Return {parameter: float}."""
    return {r["parameter"]: float(r["value"]) for r in rows(path)}


def value(name, path=PATH):
    return values(path)[name]


def source(name, path=PATH):
    for r in rows(path):
        if r["parameter"] == name:
            return r["source"]
    raise KeyError(name)


def evidence_id(name, path=PATH):
    """Evidence id named in the source column (for example S2-0033), or None."""
    s = source(name, path)
    if s.startswith("data/evidence.csv:"):
        return s.split(":", 1)[1].split()[0]
    return None


def used_by(study, path=PATH):
    """Names of the shared parameters a study uses."""
    return [r["parameter"] for r in rows(path) if study in r["used_by"].split(";")]


def link_param_rows(path=PATH):
    """Shared parameters used by the link studies, in the row format of linksim/params.csv."""
    out = []
    for r in rows(path):
        if "linksim" in r["used_by"].split(";"):
            tag = "assumption" if r["label"] == "assumption" else "cited"
            pre = "ASSUMPTION " if tag == "assumption" else ""
            out.append({"name": r["parameter"], "value": r["value"], "unit": r["unit"], "tag": tag,
                        "source": pre + "data/shared_inputs.csv (" + r["source"] + ")"})
    return out
