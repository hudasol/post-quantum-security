"""Named parameters of the planner rules (docs/PLANNER_RULES.md).

Author: Huda Mueen

Every constant is a field of Parameters. Each one can be overridden on the
command line. The tag [assumption] marks a choice that is editable by the
user. The tag [derived] marks arithmetic on a published row of the evidence
table. Derived kilobyte thresholds are lower bounds from stack optimised pqm4
rows and exclude hashing and libc.
"""

from dataclasses import dataclass, fields, replace
from fractions import Fraction

FOOTER = "This tool supports planning. It is not a security guarantee."
ESTIMATE_LABEL = "estimated from published sizes, not measured"
LOWER_BOUND_NOTE = (
    "Flash and RAM thresholds are lower bounds from published stack optimised "
    "pqm4 rows, excluding hashing and libc."
)
SYNTHETIC_BANNER = (
    "SYNTHETIC INPUT: this inventory carries a SYNTHETIC marker. The devices "
    "are invented for testing. They are not a real fleet and not measured."
)

# name: (default, tag, basis)
PARAMETER_DOC = {
    "today_year": (2026, "assumption", "date of this work"),
    "sig_horizon_year": (
        2030, "assumption",
        "EU roadmap v1.1: products with market life beyond 2030 should have "
        "PQ signed firmware updates (data/raw/S1 row 39)"),
    "conf_horizon_year": (
        2035, "assumption",
        "NCSC, EU, IR 8547 draft end dates (S1 rows 15, 33, 37)"),
    "sig_flash_kb": (
        Fraction(30), "derived",
        "ML-DSA-44 verify code 24,844 B (S2-0036) plus 4,840 B wolfBoot "
        "ML-DSA-44 example header (S4 line 85) = 29,684 B, rounded up; excludes hashing "
        "and libc; lower bound"),
    "sig_ram_kb": (
        Fraction(7), "derived",
        "ML-DSA-44 verify stack 2,712 B (S2-0036) plus the 1,312 B public key and the 2,420 B signature "
        "the verifier must hold (the stack figure excludes caller buffers) = 6,444 B, rounded up"),
    "kem_flash_kb": (
        Fraction(14), "derived", "ML-KEM-768 code 13,320 B (S2-0027), rounded up"),
    "kem_ram_kb": (
        Fraction(9), "derived",
        "ML-KEM-768 decaps stack 2,844 B (S2-0027) plus buffers 6,004 B "
        "(1184 + 1088 + 1312 + 2420) = 8,848 B, rounded up"),
    "hs_bytes": (
        6068, "derived",
        "hybrid handshake bytes: 2 x 32 B X25519 + 1184 + 1088 + 1312 + 2420"),
    "hs_budget_s": (
        Fraction(300), "assumption", "longest tolerable in band handshake"),
}


def fmt_num(value):
    """Format an int, Fraction or float without trailing zeros."""
    x = Fraction(value)
    if x.denominator == 1:
        return str(x.numerator)
    return f"{float(x):.6f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class Parameters:
    today_year: int = 2026
    sig_horizon_year: int = 2030
    conf_horizon_year: int = 2035
    sig_flash_kb: Fraction = Fraction(30)
    sig_ram_kb: Fraction = Fraction(7)
    kem_flash_kb: Fraction = Fraction(14)
    kem_ram_kb: Fraction = Fraction(9)
    hs_bytes: int = 6068
    hs_budget_s: Fraction = Fraction(300)

    def __post_init__(self):
        for name in ("today_year", "sig_horizon_year", "conf_horizon_year"):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int):
                raise ValueError(f"{name} must be an integer year")
        for name in ("sig_flash_kb", "sig_ram_kb", "kem_flash_kb", "kem_ram_kb",
                     "hs_bytes", "hs_budget_s"):
            value = getattr(self, name)
            try:
                value = Fraction(value)
            except (TypeError, ValueError):
                raise ValueError(f"{name} must be a number") from None
            if value <= 0:
                raise ValueError(f"{name} must be greater than 0")
            object.__setattr__(self, name, value)
        if self.sig_horizon_year < self.today_year:
            raise ValueError("sig_horizon_year must not be earlier than today_year")
        if self.conf_horizon_year < self.today_year:
            raise ValueError("conf_horizon_year must not be earlier than today_year")

    @property
    def sig_years(self):
        """SIG_YEARS = sig_horizon_year - today_year [derived]."""
        return self.sig_horizon_year - self.today_year

    @property
    def conf_years(self):
        """CONF_YEARS = conf_horizon_year - today_year [derived]."""
        return self.conf_horizon_year - self.today_year

    @property
    def both_flash_kb(self):
        return self.sig_flash_kb + self.kem_flash_kb

    @property
    def both_ram_kb(self):
        """The two run one after the other, so RAM is the larger of the two.

        With the default values this equals KEM_RAM_KB = 9, as in the rules.
        """
        return max(self.sig_ram_kb, self.kem_ram_kb)

    def override(self, **changes):
        changes = {k: v for k, v in changes.items() if v is not None}
        return replace(self, **changes)

    def describe(self):
        """Rows (name, value, tag, basis, overridden) in a fixed order."""
        rows = []
        for f in fields(self):
            default, tag, basis = PARAMETER_DOC[f.name]
            value = getattr(self, f.name)
            rows.append((f.name, value, tag, basis, Fraction(value) != Fraction(default)))
        rows.append(("sig_years", self.sig_years, "derived",
                     "sig_horizon_year - today_year", False))
        rows.append(("conf_years", self.conf_years, "derived",
                     "conf_horizon_year - today_year", False))
        return rows
