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


# Selective repeat closed form check (fifth round).
#
# Source: KFUPM COE 540 lecture slides (A. S. H. Mahmoud), slide 27, "Selective
# Reject ARQ, Efficiency With Errors": Nr = E[number of transmitted frames to
# successfully transmit one frame] = sum_i i P^(i-1) (1 - P) = 1 / (1 - P), with
# a data frame in error with probability P; slide 29 states that errors in
# acknowledgements are ignored. Retrieval record: netsim/SOURCES.md.
#
# linksim/sim.py selective_repeat is run unchanged. Two wrappers make its
# acknowledgements error free (the assumption of the closed form) without
# touching the module: _RecordingRadio remembers the kind of the last frame
# sent, and _DataLossRng returns "no loss" for the draw that follows an
# acknowledgement. Under that condition every data transmission, first pass or
# poll, is an independent Bernoulli trial, so the mean number of data
# transmissions per frame is 1 / (1 - P).

SR_SEED = 20261021


class _RecordingRadio(sim.Radio):
    def __init__(self, link, stats):
        sim.Radio.__init__(self, link, stats)
        self.last_kind = "data"

    def send(self, who, t_ready, wire_bytes, kind="data"):
        self.last_kind = kind
        return sim.Radio.send(self, who, t_ready, wire_bytes, kind)


class _DataLossRng:
    """Random source for sim.selective_repeat: draws after an acknowledgement
    return 1.0 (never lost) when ack_loss is False."""

    def __init__(self, seed, radio, ack_loss=False):
        self.rng = random.Random(seed)
        self.radio = radio
        self.ack_loss = ack_loss

    def random(self):
        u = self.rng.random()
        if not self.ack_loss and self.radio.last_kind == "ack":
            return 1.0
        return u


def sr_transmissions_sim(link_key, p_loss, trials=2000, seed=SR_SEED, p=None,
                         n_frames=50, ack_loss=False):
    """Mean data transmissions per frame of linksim's selective repeat, one
    value per trial (n_frames frames per trial, seeds seed, seed + 1, ...).
    Closed form with error free acknowledgements: 1 / (1 - p_loss)."""
    p = p or model.load_params()
    link = model.build_links(p)[link_key]
    sizes = [link.wire_bytes(link.cap)] * int(n_frames)
    out = []
    for i in range(trials):
        st = sim.Stats()
        radio = _RecordingRadio(link, st)
        rng = _DataLossRng(seed + i, radio, ack_loss)
        _, ok = sim.selective_repeat(radio, rng, p_loss, "A", "B", sizes, p, 0.0)
        if not ok:
            continue
        out.append(st.data_frames_sent / float(len(sizes)))
    return out


def sr_closed_form(p_loss):
    """Expected transmissions per frame for selective repeat with independent
    frame loss p_loss and error free acknowledgements: 1 / (1 - p_loss)."""
    return 1.0 / (1.0 - p_loss)


SR_LOSSES = (0.01, 0.05, 0.1, 0.2, 0.3)
SR_BLOCK = 1000000


def sr_seed_block(k, seed=SR_SEED):
    """First seed of the independent block for loss rate index k."""
    return seed + SR_BLOCK * (k + 1)


def sr_check_rows(trials=2000, link_key="ieee802154", n_frames=50, p=None):
    """Closed form check rows, one independent seed block per loss rate.
    Rows with ack_loss True run the simulation as the studies do (the same
    loss on acknowledgements); the closed form then is only a lower bound,
    and 1 / (1 - p)^2 an upper bound (every frame sent as a poll)."""
    p = p or model.load_params()
    rows = []
    for ack_loss in (False, True):
        for k, q in enumerate(SR_LOSSES):
            s0 = sr_seed_block(k + (len(SR_LOSSES) if ack_loss else 0))
            vals = sr_transmissions_sim(link_key, q, trials, s0, p, n_frames, ack_loss)
            r = check_row(q, vals, sr_closed_form(q))
            r.update({"label": "modelled", "link": link_key, "n_frames": n_frames,
                      "ack_loss": ack_loss, "upper_bound": 1.0 / (1.0 - q) ** 2,
                      "inside_bounds": r["ci_hi"] >= r["closed_form"] and r["ci_lo"] <= 1.0 / (1.0 - q) ** 2,
                      "seed_first": s0, "seed_last": s0 + trials - 1,
                      "trials_completed": len(vals), "trials_run": trials})
            rows.append(r)
    return rows
