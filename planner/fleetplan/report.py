"""Output formatters: table, csv, json and md.

Author: Huda Mueen

Every format carries the SYNTHETIC banner when the input is marked, the
summary counts, the handshake label and the planning footer.
"""

import csv
import io
import json

from .classify import summarise
from .rules import ESTIMATE_LABEL, FOOTER, LOWER_BOUND_NOTE, SYNTHETIC_BANNER, fmt_num

COLUMNS = ("device_id", "class", "reasons", "missing_fields", "handshake_s_estimate", "flags")
REASON_SEP = " | "
LIST_SEP = ";"


def _hs(value):
    return "" if value is None else f"{value:.3f}"


def _summary_text(results):
    counts = summarise(results)
    parts = "; ".join(f"{k} {v}" for k, v in counts.items())
    return f"Summary: {len(results)} devices; {parts}"


def _hs_note():
    return f"handshake_s_estimate is in seconds, {ESTIMATE_LABEL}."


def _param_rows(params):
    return params.describe()


def render_csv(inv, results, params, explain=False):
    out = io.StringIO()
    if inv.synthetic:
        out.write(f"# {SYNTHETIC_BANNER}\n")
    out.write("# Lines starting with # are comments.\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for r in results:
        writer.writerow([r.device_id, r.cls, REASON_SEP.join(r.reasons),
                         LIST_SEP.join(r.missing_fields), _hs(r.handshake_s),
                         LIST_SEP.join(r.flags)])
    out.write(f"# {_summary_text(results)}\n")
    out.write(f"# {_hs_note()}\n")
    out.write(f"# {LOWER_BOUND_NOTE}\n")
    out.write(f"# {FOOTER}\n")
    return out.getvalue()


def render_json(inv, results, params, explain=False):
    doc = {
        "banner": SYNTHETIC_BANNER if inv.synthetic else None,
        "input": inv.source,
        "synthetic": inv.synthetic,
        "parameters": [
            {"name": n, "value": float(v) if hasattr(v, "denominator") and v.denominator != 1 else int(v),
             "tag": t, "basis": b, "overridden": o}
            for n, v, t, b, o in _param_rows(params)],
        "devices": [
            {"device_id": r.device_id, "class": r.cls, "reasons": list(r.reasons),
             "missing_fields": list(r.missing_fields),
             "handshake_s_estimate": None if r.handshake_s is None else round(r.handshake_s, 3),
             "flags": list(r.flags)} for r in results],
        "summary": {"total": len(results), "counts": summarise(results)},
        "notes": [_hs_note(), LOWER_BOUND_NOTE],
        "footer": FOOTER,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _table(rows):
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    lines = []
    for n, row in enumerate(rows):
        lines.append("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)).rstrip())
        if n == 0:
            lines.append("  ".join("-" * w for w in widths))
    return lines


def render_table(inv, results, params, explain=False):
    lines = []
    if inv.synthetic:
        lines += [SYNTHETIC_BANNER, ""]
    lines.append(f"Fleet migration plan for {inv.source}")
    lines.append("")
    if explain:
        lines.append("Parameters (value, tag, basis)")
        for n, v, t, b, o in _param_rows(params):
            lines.append(f"  {n} = {fmt_num(v)} [{t}]{' (overridden)' if o else ''}: {b}")
        lines.append("")
    rows = [("device_id", "class", "handshake_s", "missing_fields", "flags", "first reason")]
    for r in results:
        rows.append((r.device_id, r.cls, _hs(r.handshake_s) or "-",
                     LIST_SEP.join(r.missing_fields) or "-",
                     LIST_SEP.join(r.flags) or "-", r.reasons[0]))
    lines += _table(rows)
    if explain:
        lines += ["", "Explanations"]
        for r in results:
            lines.append(f"{r.device_id}  {r.cls}")
            for i, reason in enumerate(r.reasons, start=1):
                lines.append(f"    {i}. {reason}")
    lines += ["", _summary_text(results), _hs_note(), LOWER_BOUND_NOTE, FOOTER]
    return "\n".join(lines) + "\n"


def _esc(text):
    return str(text).replace("|", "\\|")


def render_md(inv, results, params, explain=False):
    lines = []
    if inv.synthetic:
        lines += [f"> **{SYNTHETIC_BANNER}**", ""]
    lines += [f"# Fleet migration plan", "", f"Input: `{inv.source}`", ""]
    if explain:
        lines += ["## Parameters", "", "| Name | Value | Tag | Basis |", "|---|---|---|---|"]
        for n, v, t, b, o in _param_rows(params):
            lines.append(f"| {n} | {fmt_num(v)}{' (overridden)' if o else ''} | {t} | {_esc(b)} |")
        lines.append("")
    lines += ["## Devices", "",
              "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in results:
        lines.append("| " + " | ".join(_esc(c) for c in (
            r.device_id, r.cls, REASON_SEP.join(r.reasons), LIST_SEP.join(r.missing_fields),
            _hs(r.handshake_s), LIST_SEP.join(r.flags))) + " |")
    lines += ["", "## Summary", ""]
    for k, v in summarise(results).items():
        lines.append(f"- {k}: {v}")
    lines.append(f"- total: {len(results)}")
    lines += ["", _hs_note(), "", LOWER_BOUND_NOTE, "", f"*{FOOTER}*"]
    return "\n".join(lines) + "\n"


RENDERERS = {"table": render_table, "csv": render_csv, "json": render_json, "md": render_md}
