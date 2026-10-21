"""linksim values at the settings of the ns-3 cells, and the closed form check.

Author: Huda Mueen.

Run from the repository root:  python3 -m netsim.compare
Writes netsim/results/linksim_same_settings.csv, linksim_lora_toa.csv,
linksim_lora_flights.csv (label modelled) and sr_closed_form.csv (label
modelled). Needs no ns-3. Size and timing arithmetic only.
"""
import csv
import os

from linksim import checks, lora, mac802154, model, validate_v4

from . import cells

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "netsim", "results")
LABEL = "modelled"


def wall(p, over=None, hops=1):
    q = dict(p)
    if over:
        q.update(over)
    t = validate_v4.wall_802154(q, mac802154.FLAGS, nbytes=cells.OBJECT_BYTES)
    return mac802154.multihop_wall_s(t, hops), t


def linksim_cell(c, p):
    """(time_s, note) of linksim's diagnosis model (steps 1 to 6 of
    docs/LINKSIM_STUDY.md Section 4.4) at the setting of ns-3 cell c."""
    a = c["args"]
    over = {}
    notes = []
    if a["minBe"] != cells.BASE["minBe"]:
        over["ieee802154_min_be"] = a["minBe"]
        notes.append("mean initial backoff with macMinBE %d" % a["minBe"])
    if a["maxBe"] != cells.BASE["maxBe"]:
        over["ieee802154_max_be"] = a["maxBe"]
        notes.append("macMaxBE has no effect in the model (no busy channel)")
    if a["maxBackoffs"] != cells.BASE["maxBackoffs"]:
        over["ieee802154_max_csma_backoffs"] = a["maxBackoffs"]
        notes.append("macMaxCSMABackoffs has no effect in the model (no busy channel)")
    if a["retries"] != cells.BASE["retries"]:
        notes.append("frame retries have no effect in the model (no loss)")
    if a["bgNodes"]:
        notes.append("contention not modelled")
    if a["hops"] > 1:
        notes.append("hops by store and forward without spatial reuse (ASSUMPTION of Section 4.4)")
    if a["segBytes"] == cells.SEG_DGRAM:
        notes.append("model always uses 1280 B datagrams")
    t, _ = wall(p, over, a["hops"])
    return t, "; ".join(notes) or "diagnosis steps 1 to 6, no loss"


def linksim_rows(p=None):
    p = p or model.load_params()
    rows = []
    for c in cells.lrwpan_cells():
        t, note = linksim_cell(c, p)
        rows.append({"label": LABEL, "cell": c["cell"], "cause": c["cause"], "value": c["value"],
                     "time_s_linksim": t, "note": note})
    return rows


def lora_toa_rows(p=None):
    p = p or model.load_params()
    rows = []
    for dr in (0, 5):
        sf = int(p["lora_dr0_sf"] if dr == 0 else p["lora_dr5_sf"])
        for n in cells.LORA_TOA_SIZES:
            t = lora.time_on_air_s(n, sf, p["lora_bw_hz"], int(p["lora_coding_rate_index"]),
                                   p["lora_preamble_symbols"], 1, 0, None, p["lora_header_extra_symbols"])
            rows.append({"label": LABEL, "dr": dr, "phy_payload_bytes": n, "toa_s_linksim": t})
    return rows


def lora_flight_rows(p=None):
    """linksim totals for the handshake flights: the no acknowledgement blast
    (same structure as the ns-3 run) and the protocol simulation with
    selective repeat acknowledgements (linksim/protocols.py run_once at zero
    loss on the same frozen flights as the ns-3 run; before design change F1
    this equalled handshake_mean_s of linksim/results/protocols_grid.csv)."""
    from linksim import protocols as lp
    p = p or model.load_params()
    grid = {}
    for prot, flights in cells.lora_flights():
        for dr in (0, 5):
            fl = [(s, "flight", b) for s, b in flights]
            r = lp.run_once(lp.build_link("lora_dr%d" % dr, p), fl, 0.0, lp.SEED, p)
            grid[(prot, "lora_dr%d" % dr)] = r["wall_s"]
    rows = []
    for prot, flights in cells.lora_flights():
        for dr in (0, 5):
            link = lora.LoraLink(p, dr)
            blast = sum(model.blast_wall_s(link, b) for _, b in flights)
            link9 = lora.LoraLink(p, dr)
            link9.mac = cells.NS3_LORAWAN_OVERHEAD_BYTES
            blast9 = sum(model.blast_wall_s(link9, b) for _, b in flights)
            frags = sum(len(model.fragment_wire_sizes(link, b)) for _, b in flights)
            rows.append({"label": LABEL, "protocol": prot, "dr": dr, "fragments": frags,
                         "blast_s_linksim": blast, "blast_9b_s_linksim": blast9,
                         "protocol_sim_s_linksim": grid.get((prot, "lora_dr%d" % dr), "")})
    return rows


FOLLOWUP_LOSS = 0.3
FOLLOWUP_BLOCKS = 10
FOLLOWUP_SEED = 40000000


def sr_followup_rows(trials=2000, p=None):
    """Follow up added after the first run, in which the error free row at
    loss 0.3 fell outside its interval: ten further independent seed blocks
    at the same loss, each reported, and their pooled mean."""
    p = p or model.load_params()
    rows = []
    pooled = []
    for b in range(FOLLOWUP_BLOCKS):
        s0 = FOLLOWUP_SEED + b * 10000
        v = checks.sr_transmissions_sim("ieee802154", FOLLOWUP_LOSS, trials, s0, p)
        pooled += v
        r = checks.check_row(FOLLOWUP_LOSS, v, checks.sr_closed_form(FOLLOWUP_LOSS))
        r.update({"label": LABEL, "link": "ieee802154", "n_frames": 50, "ack_loss": False,
                  "upper_bound": 1.0 / (1.0 - FOLLOWUP_LOSS) ** 2, "inside_bounds": "",
                  "seed_first": s0, "seed_last": s0 + trials - 1, "trials_completed": len(v),
                  "trials_run": trials, "role": "follow up block %d" % (b + 1)})
        rows.append(r)
    r = checks.check_row(FOLLOWUP_LOSS, pooled, checks.sr_closed_form(FOLLOWUP_LOSS))
    r.update({"label": LABEL, "link": "ieee802154", "n_frames": 50, "ack_loss": False,
              "upper_bound": 1.0 / (1.0 - FOLLOWUP_LOSS) ** 2, "inside_bounds": "",
              "seed_first": FOLLOWUP_SEED, "seed_last": FOLLOWUP_SEED + (FOLLOWUP_BLOCKS - 1) * 10000 + trials - 1,
              "trials_completed": len(pooled), "trials_run": trials * FOLLOWUP_BLOCKS,
              "role": "follow up pooled"})
    rows.append(r)
    return rows


def sr_rows(trials=2000):
    rows = checks.sr_check_rows(trials=trials)
    for r in rows:
        r["role"] = "pre set check" if not r["ack_loss"] else "studies as run (acknowledgements lost too)"
    return rows + sr_followup_rows(trials)


def write(name, rows, fields):
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("%.6g" % r[k]) if isinstance(r.get(k), float) else r.get(k, "") for k in fields})


SR_FIELDS = ["label", "role", "link", "n_frames", "ack_loss", "loss", "trials_run", "trials_completed", "mean_tx",
             "ci_lo", "ci_hi", "closed_form", "inside", "upper_bound", "inside_bounds", "seed_first",
             "seed_last"]


def main():
    p = model.load_params()
    write("linksim_same_settings.csv", linksim_rows(p),
          ["label", "cell", "cause", "value", "time_s_linksim", "note"])
    write("linksim_lora_toa.csv", lora_toa_rows(p), ["label", "dr", "phy_payload_bytes", "toa_s_linksim"])
    write("linksim_lora_flights.csv", lora_flight_rows(p),
          ["label", "protocol", "dr", "fragments", "blast_s_linksim", "blast_9b_s_linksim",
           "protocol_sim_s_linksim"])
    write("sr_closed_form.csv", sr_rows(), SR_FIELDS)
    print("wrote linksim_same_settings.csv linksim_lora_toa.csv linksim_lora_flights.csv sr_closed_form.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
