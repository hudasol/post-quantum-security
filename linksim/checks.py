"""Closed form checks of the link simulator (fourth round).

Author: Huda Mueen. Size and timing arithmetic only; no cryptographic
operation. Seed 20261020 unless stated.
"""
import math
import random

from . import model, sim

SEED = 20261020
Z95 = 1.959963984540054


def duty_wait_closed_form(air_s, duty):
    """Silence required after air_s at duty fraction duty: air (1/duty - 1).
    At 1 percent this is 99 x air."""
    return air_s * (1.0 / duty - 1.0)


def mean_ci(values):
    n = len(values)
    m = sum(values) / n
    sd = math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    h = Z95 * sd / math.sqrt(n)
    return m, m - h, m + h


def sw_transmissions_data_loss(p_loss, trials=2000, seed=SEED, max_tries=1000):
    """Stop and wait, one fragment per trial, independent Bernoulli loss on the
    data frame only (acknowledgements never lost). Returns the list of
    transmissions per fragment. Closed form mean: 1 / (1 - p)."""
    rng = random.Random(seed)
    out = []
    for _ in range(trials):
        k = 0
        while True:
            k += 1
            if rng.random() >= p_loss or k >= max_tries:
                break
        out.append(k)
    return out


def sw_transmissions_sim(link_key, p_loss, trials=2000, seed=SEED, p=None):
    """Transmissions per fragment from the existing event simulation
    (sim.stop_and_wait), where data and acknowledgements are both lost with
    probability p. One fragment per trial, seeds seed, seed + 1, ...
    Closed form mean when no transfer fails: 1 / (1 - p)^2."""
    p = p or model.load_params()
    link = model.build_links(p)[link_key]
    out = []
    for i in range(trials):
        st = sim._run_flights(link, [("A", "one fragment", link.cap)], "sw", p_loss,
                              seed + i, p)
        out.append(st.data_frames_sent)
    return out


def check_row(p_loss, values, closed):
    m, lo, hi = mean_ci(values)
    return {"loss": p_loss, "trials": len(values), "mean_tx": m, "ci_lo": lo, "ci_hi": hi,
            "closed_form": closed, "inside": lo <= closed <= hi}
