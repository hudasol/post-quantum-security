"""Classification of one device by the rules in docs/PLANNER_RULES.md.

Author: Huda Mueen

Each result holds the class, a list of reason strings (the first one is the
deciding reason, and every reason cites a rule number), the missing fields,
the flags, and the handshake time estimate. UNKNOWN is returned whenever
required information is missing or unparseable. Nothing is guessed.
"""

from dataclasses import dataclass
from fractions import Fraction

from .loader import REQUIRED_COLUMNS
from .rules import ESTIMATE_LABEL, Parameters, fmt_num

UNKNOWN = "UNKNOWN"
NO_ACTION = "NO_ACTION_BEFORE_RETIREMENT"
FIRMWARE_UPDATE = "FIRMWARE_UPDATE"
HYBRID = "HYBRID"
HARDWARE_REPLACEMENT = "HARDWARE_REPLACEMENT"
CLASSES = (FIRMWARE_UPDATE, HYBRID, HARDWARE_REPLACEMENT,
           NO_ACTION, UNKNOWN)

FLAG_FIFTH_CLASS = "FIFTH_CLASS_DEVIATION"
FLAG_GATEWAY = "GATEWAY_REQUIRED"
FLAG_HS_OVER = "HS_OVER_BUDGET"


@dataclass(frozen=True)
class Result:
    device_id: str
    cls: str
    reasons: tuple
    missing_fields: tuple
    handshake_s: object  # float seconds or None
    flags: tuple


def _names(names):
    return ", ".join(names) + (" is" if len(names) == 1 else " are")


def _headroom(rec, need_flash, need_ram):
    """Rule 5. Return (verdict, text, missing) with verdict enough, insufficient or unknown."""
    f = rec.fields
    parts = []
    short = False
    missing = []
    for free_name, total_name, need in (("free_flash_kb", "flash_kb", need_flash),
                                        ("free_ram_kb", "ram_kb", need_ram)):
        free, total = f[free_name], f[total_name]
        need_s = fmt_num(need)
        if free.status == "ok":
            if free.value >= need:
                parts.append(f"{free_name} {fmt_num(free.value)} kB meets need {need_s} kB")
            else:
                short = True
                parts.append(f"{free_name} {fmt_num(free.value)} kB is below need {need_s} kB")
        elif total.value < need:
            short = True
            why = "unparseable" if free.status == "invalid" else "not known"
            parts.append(f"{free_name} {why} and {total_name} {fmt_num(total.value)} kB "
                         f"is already below need {need_s} kB")
        else:
            missing.append(free_name)
            why = f"unparseable ({free.detail})" if free.status == "invalid" else "not known"
            parts.append(f"{free_name} {why}")
    detail = "; ".join(parts)
    if short:
        return "insufficient", f"Rule 5: headroom insufficient, {detail}", ()
    if missing:
        return "unknown", f"Rule 5: headroom cannot be decided, {detail}", tuple(missing)
    return "enough", f"Rule 5: headroom sufficient, {detail}", ()


def classify(rec, params=None):
    """Classify one Record and return a Result."""
    p = params or Parameters()
    f = rec.fields
    flags = []
    for name in ("free_flash_kb", "free_ram_kb", "updatable_bootloader_stage"):
        if f[name].status == "invalid":
            flags.append(f"INVALID_OPTIONAL:{name}")

    bw = f["link_bandwidth_bps"]
    hs = None
    hs_exact = None
    if bw.status == "ok":
        hs_exact = Fraction(p.hs_bytes) * 8 / bw.value
        hs = float(hs_exact)
    support = []
    if hs is not None:
        support.append(
            f"Rule 8: handshake time {hs:.3f} s for {fmt_num(p.hs_bytes)} bytes at "
            f"{fmt_num(bw.value)} bit/s ({ESTIMATE_LABEL})")

    def done(cls, decision, missing=(), extra_support=()):
        reasons = (decision,) + tuple(extra_support) + tuple(support)
        return Result(rec.device_id, cls, reasons, tuple(missing), hs, tuple(flags))

    # Rule 1
    bad = [n for n in REQUIRED_COLUMNS if f[n].status != "ok"]
    if bad:
        detail = "; ".join(f"{n} ({f[n].detail})" for n in bad)
        return done(UNKNOWN, f"Rule 1: required field(s) missing or unparseable, "
                             f"no class assigned: {detail}", bad)

    # Rule 2
    svc = f["service_life_remaining_years"].value
    data = f["data_lifetime_years"].value
    sig = svc > p.sig_years
    conf = data > p.conf_years
    r2 = (f"Rule 2: service_life_remaining_years {fmt_num(svc)} "
          f"{'>' if sig else '<='} SIG_YEARS {p.sig_years}, so signature "
          f"{'exposed' if sig else 'not exposed'}; data_lifetime_years {fmt_num(data)} "
          f"{'>' if conf else '<='} CONF_YEARS {p.conf_years}, so confidentiality "
          f"{'exposed' if conf else 'not exposed'} (strictly greater is exposed)")

    # Rule 3
    if not sig and not conf:
        flags.append(FLAG_FIFTH_CLASS)
        return done(NO_ACTION, "Rule 3: neither signature nor confidentiality is exposed "
                               "(fifth class, flagged deviation from the four requested classes)",
                    (), (r2,))

    # Rule 4
    if sig and conf:
        nf, nr, what = p.both_flash_kb, p.both_ram_kb, "signature and KEM"
    elif sig:
        nf, nr, what = p.sig_flash_kb, p.sig_ram_kb, "signature only"
    else:
        nf, nr, what = p.kem_flash_kb, p.kem_ram_kb, "KEM only"
    r4 = f"Rule 4: need for {what} is {fmt_num(nf)} kB flash and {fmt_num(nr)} kB RAM"
    extra = [r2, r4]

    def hs_note(converted):
        if conf and hs_exact > p.hs_budget_s and not converted:
            flags.append(FLAG_HS_OVER)
            extra.append(
                f"Rule 7 gateway conversion not applied: it applies only when confidentiality "
                f"is the only exposure and the result is FIRMWARE_UPDATE; handshake "
                f"{hs:.3f} s exceeds HS_BUDGET_S {fmt_num(p.hs_budget_s)} s, flagged for review")

    verdict, htext, hmissing = _headroom(rec, nf, nr)

    if sig:
        updatable = f["bootrom_verifier_updatable"].value
        if updatable:
            extra.append(htext)
            if verdict == "unknown":
                hs_note(False)
                return done(UNKNOWN, "Rule 5: no class assigned because "
                            + _names(hmissing) + " not known and the need cannot be ruled out",
                            hmissing, extra)
            hs_note(False)
            if verdict == "enough":
                return done(FIRMWARE_UPDATE,
                            "Rule 6: signature exposed, bootrom_verifier_updatable = yes and "
                            "headroom is enough, so a firmware update can carry the PQ verifier",
                            (), extra)
            return done(HARDWARE_REPLACEMENT,
                        "Rule 6: signature exposed, bootrom_verifier_updatable = yes but "
                        "headroom is insufficient, so hardware replacement", (), extra)
        stage = f["updatable_bootloader_stage"]
        if stage.status != "ok":
            hs_note(False)
            why = "unparseable" if stage.status == "invalid" else "blank"
            return done(UNKNOWN,
                        f"Rule 6: signature exposed, bootrom_verifier_updatable = no and "
                        f"updatable_bootloader_stage is {why}, so no class assigned",
                        ("updatable_bootloader_stage",), extra)
        if not stage.value:
            hs_note(False)
            return done(HARDWARE_REPLACEMENT,
                        "Rule 6: signature exposed, bootrom_verifier_updatable = no and "
                        "updatable_bootloader_stage = no, so hardware replacement", (), extra)
        extra.append(htext)
        hs_note(False)
        if verdict == "unknown":
            return done(UNKNOWN, "Rule 5: no class assigned because "
                        + _names(hmissing) + " not known and the need cannot be ruled out",
                        hmissing, extra)
        if verdict == "enough":
            return done(HYBRID,
                        "Rule 6: signature exposed, bootrom_verifier_updatable = no, "
                        "updatable_bootloader_stage = yes and headroom is enough, so HYBRID: "
                        "the classical root stays, the PQ verifier goes in the updatable stage, "
                        "and an image is accepted only if both signatures verify", (), extra)
        return done(HARDWARE_REPLACEMENT,
                    "Rule 6: signature exposed, bootrom_verifier_updatable = no, "
                    "updatable_bootloader_stage = yes but headroom is insufficient, "
                    "so hardware replacement", (), extra)

    # Rule 7: confidentiality is the only exposure
    extra.append(htext)
    if verdict == "unknown":
        hs_note(False)
        return done(UNKNOWN, "Rule 5: no class assigned because "
                    + _names(hmissing) + " not known and the need cannot be ruled out",
                    hmissing, extra)
    if verdict == "insufficient":
        hs_note(False)
        return done(HARDWARE_REPLACEMENT,
                    "Rule 7: only confidentiality is exposed and headroom for the KEM is "
                    "insufficient, so hardware replacement", (), extra)
    if hs_exact > p.hs_budget_s:
        flags.append(FLAG_GATEWAY)
        return done(HYBRID,
                    f"Rule 7: only confidentiality is exposed and headroom is enough, but the "
                    f"estimated handshake {hs:.3f} s exceeds HS_BUDGET_S {fmt_num(p.hs_budget_s)} s, "
                    f"so FIRMWARE_UPDATE becomes HYBRID: terminate the PQ session at a gateway "
                    f"and keep the classical hop on the device", (), extra)
    return done(FIRMWARE_UPDATE,
                "Rule 7: only confidentiality is exposed, headroom for the KEM is enough and the "
                "estimated handshake is within HS_BUDGET_S, so a firmware update", (), extra)


def classify_all(inventory, params=None):
    """Classify every record, keeping input order."""
    return [classify(r, params) for r in inventory.records]


def summarise(results):
    counts = {c: 0 for c in CLASSES}
    for r in results:
        counts[r.cls] += 1
    return counts
