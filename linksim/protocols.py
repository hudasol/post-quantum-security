"""Seeded discrete event simulation of secure session protocols over narrow links.

Author: Huda Mueen.

Run from the repository root:  python -m linksim.protocols [--trials 1000]
Writes linksim/results/protocols_*.csv. Then python -m linksim.protocols_report
writes docs/PROTOCOL_SIM.md and the figures.

Messages are byte counts; no cryptographic operation is performed and no
protocol is implemented. Flight structures are simplified, conceptual
profiles of DTLS 1.3, EDHOC with OSCORE, a MAVLink 2 style signed stream with
a post quantum session handshake, and a ROS 2 DDS Security style
authentication handshake. Sizes:
  key shares, signatures, public keys: linksim/params.csv rows citing
  data/evidence.csv (S2-0399, S2-0401, S2-0406, S2-0407, S3-018, S3-019) and
  data/raw/S3_robotics.md;
  EDHOC message framing: draft-ietf-lake-edhoc-17 Figure 1
  (data/raw/S12_link_sources.md:79) minus a 32 B share and a 64 B signature
  (that split is an ASSUMPTION);
  DTLS, OSCORE, DDS framing and certificate overhead: ASSUMPTIONS (params.csv),
  swept in the sensitivity analysis.
Label of every output: modelled (the link timing model has the validation
errors of Section 4.4 of docs/LINKSIM_STUDY.md beside it).
"""
import argparse
import csv
import math
import os
import random
import time
from multiprocessing import Pool

from . import lora, mac802154, model, montecarlo as mc, sim

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "linksim", "results")
SEED = 20261020
TRIALS = 1000
LOSSES = (0.0, 0.01, 0.05, 0.10, 0.20)
DEADLINES_S = (1.0, 2.0, 5.0, 10.0, 60.0, 600.0, 1800.0, 3600.0)
PROTOCOLS = ("dtls13", "edhoc_oscore", "mavlink2_pq", "dds_security")
VARIANTS = ("classical", "hybrid", "pq_only")
RAW = ("raw_mldsa44", "per_message")
LINKS = ("lora_dr0", "lora_dr5", "ieee802154", "sik")
LINK_LABEL = {"lora_dr0": "LoRaWAN EU868 DR0", "lora_dr5": "LoRaWAN EU868 DR5",
              "ieee802154": "IEEE 802.15.4 (v4 frame model)", "sik": "SiK 64 kbps"}
LABEL = "modelled"


def build_link(key, p):
    if key == "lora_dr0":
        return lora.LoraLink(p, 0)
    if key == "lora_dr5":
        return lora.LoraLink(p, 5)
    if key == "ieee802154":
        return mac802154.build(p, mac802154.FLAGS)
    if key == "sik":
        return model.build_links(p)["sik"]
    raise ValueError(key)


def crypto_sizes(p, variant):
    """(initiator share, responder share, signature, public key) in bytes."""
    if variant == "classical":
        x = p["x25519_share_bytes"]
        return x, x, p["ed25519_sig_bytes"], p["ed25519_pk_bytes"]
    if variant == "hybrid":
        return (p["x25519mlkem768_client_share_bytes"], p["x25519mlkem768_server_share_bytes"],
                p["mldsa44_sig_bytes"], p["mldsa44_pk_bytes"])
    if variant == "pq_only":
        return (p["mlkem768_ek_bytes"], p["mlkem768_ct_bytes"], p["mldsa44_sig_bytes"],
                p["mldsa44_pk_bytes"])
    raise ValueError(variant)


def cert_bytes(p, variant):
    _, _, sig, pk = crypto_sizes(p, variant)
    return pk + sig + p["proto_cert_overhead_bytes"]


def handshake_flights(protocol, variant, p):
    """List of (sender, label, bytes); A is the ground side, B the vehicle."""
    if protocol == "raw_mldsa44":
        return []
    kc, ks, sig, pk = crypto_sizes(p, variant)
    if protocol == "dtls13":
        fr = p["proto_dtls_handshake_framing_bytes"]
        c = cert_bytes(p, variant)
        f = [("A", "ClientHello", fr + kc), ("B", "ServerHello to Finished", fr + ks + c + sig),
             ("A", "client Certificate to Finished", fr + c + sig)]
    elif protocol == "edhoc_oscore":
        coap = p["proto_coap_header_bytes"]
        x, s64 = p["x25519_share_bytes"], p["ed25519_sig_bytes"]
        f = [("A", "EDHOC message_1", p["edhoc_sig_kid_m1_bytes"] - x + kc + coap),
             ("B", "EDHOC message_2", p["edhoc_sig_kid_m2_bytes"] - x - s64 + ks + sig + coap),
             ("A", "EDHOC message_3", p["edhoc_sig_kid_m3_bytes"] - s64 + sig + coap)]
    elif protocol == "mavlink2_pq":
        # Same structure as the mission study and the formal models with design change F1
        # (docs/FORMAL_VERIFICATION.md): both sides sign the transcript with pinned keys (no public key
        # on the air) and each sends a key confirmation tag.
        f = [("A", "F1 key share", kc), ("B", "F2 key share", ks),
             ("A", "F3 ground signature and confirmation", sig + p["confirm_bytes"]),
             ("B", "F4 vehicle signature and confirmation", sig + p["confirm_bytes"])]
    elif protocol == "dds_security":
        fr = p["proto_dds_handshake_framing_bytes"]
        c = cert_bytes(p, variant)
        f = [("A", "HandshakeRequest", fr + c + kc), ("B", "HandshakeReply", fr + c + ks + sig),
             ("A", "HandshakeFinal", fr + sig)]
    else:
        raise ValueError(protocol)
    return [(s, lab, int(round(b))) for s, lab, b in f]


def rekey_flights(protocol, variant, p):
    """Fresh ephemeral key exchange inside the existing session, no
    certificates or signatures (ASSUMPTION for every protocol): share each way
    plus per message protection overhead and a 16 B confirmation."""
    if protocol == "raw_mldsa44":
        return []
    kc, ks, _, _ = crypto_sizes(p, variant)
    o = command_overhead(protocol, variant, p)
    return [("A", "rekey share", int(kc + o)), ("B", "rekey share and confirmation",
                                                int(ks + o + p["confirm_bytes"]))]


def command_base_bytes(p):
    """Unprotected command: MAVLink 2 header and checksum plus a 30 B payload."""
    return int(p["mav_header_bytes"] + p["mav_checksum_bytes"] + p["msg_payload_bytes"])


def command_overhead(protocol, variant, p):
    if protocol == "dtls13":
        return p["proto_dtls_record_overhead_bytes"]
    if protocol == "edhoc_oscore":
        return p["proto_oscore_overhead_bytes"]
    if protocol == "mavlink2_pq":
        return p["mav_sig_field_bytes"]
    if protocol == "dds_security":
        return p["proto_dds_message_overhead_bytes"]
    if protocol == "raw_mldsa44":
        return p["mldsa44_sig_bytes"]
    raise ValueError(protocol)


def firmware_flights(variant, p):
    sig = p["ed25519_sig_bytes"] if variant == "classical" else p["mldsa44_sig_bytes"]
    return [("A", "firmware image and signature", int(p["fw_image_bytes"] + sig))]


class SideRadio(sim.Radio):
    """Radio that also records air time per transmitter."""

    def __init__(self, link, stats):
        sim.Radio.__init__(self, link, stats)
        self.side_air = {"A": 0.0, "B": 0.0}

    def send(self, who, t_ready, wire_bytes, kind="data"):
        s, e = sim.Radio.send(self, who, t_ready, wire_bytes, kind)
        self.side_air[who] += e - s
        return s, e


def run_once(link, flights, loss, seed, p, proto="sr"):
    """One seeded run. Returns dict: wall_s, completed, air_s, side_air_max_s,
    flight_ends (cumulative end time of each flight)."""
    rng = random.Random(seed)
    st = sim.Stats()
    radio = SideRadio(link, st)
    t = 0.0
    ends = []
    ok = True
    for sender, label, nbytes in flights:
        rcv = "B" if sender == "A" else "A"
        sizes = model.fragment_wire_sizes(link, nbytes)
        t, ok = sim.PROTOS[proto](radio, rng, loss, sender, rcv, sizes, p, t)
        ends.append(t)
        if not ok:
            break
    return {"wall_s": t, "completed": ok, "air_s": st.air_s,
            "side_air_max_s": max(radio.side_air.values()), "flight_ends": ends}


def configs():
    out = [(pr, v) for pr in PROTOCOLS for v in VARIANTS]
    out.append(RAW)
    return out


def scenario_flights(scenario, protocol, variant, p):
    if scenario == "firmware":
        return firmware_flights(variant, p)
    cmd = ("A", "authenticated command",
           int(command_base_bytes(p) + command_overhead(protocol, variant, p)))
    if scenario == "ttfam":
        return handshake_flights(protocol, variant, p) + [cmd]
    if scenario == "rekey":
        return rekey_flights(protocol, variant, p)
    if scenario == "firmware":
        return firmware_flights(variant, p)
    raise ValueError(scenario)


def cell(args):
    """One grid cell: (scenario, link key, protocol, variant, loss, trials, p)."""
    scenario, lk, protocol, variant, loss, trials, p = args
    link = build_link(lk, p)
    flights = scenario_flights(scenario, protocol, variant, p)
    det = loss == 0.0
    runs = [run_once(link, flights, loss, SEED, p)] if det else \
        [run_once(link, flights, loss, SEED + i, p) for i in range(trials)]
    if det:
        runs = runs * trials
    done = [r for r in runs if r["completed"]]
    walls = [r["wall_s"] for r in done]
    s = mc.summarise(walls)
    lo, hi = mc.wilson(len(done), trials)
    row = {"label": LABEL, "scenario": scenario, "link": lk, "protocol": protocol, "variant": variant,
           "loss": loss, "trials": trials, "seed_first": SEED, "seed_last": SEED + trials - 1,
           "deterministic": det, "bytes_total": sum(b for _, _, b in flights),
           "flights": len(flights), "completion": len(done) / trials, "completion_lo": lo,
           "completion_hi": hi}
    row.update({"wall_" + k: s[k] for k in ("mean", "ci_lo", "ci_hi", "median", "p05", "p95")})
    if scenario == "ttfam" and done and len(flights) > 1:
        hs = [r["flight_ends"][-2] for r in done]
        row["handshake_mean_s"] = sum(hs) / len(hs)
    for d in DEADLINES_S:
        k = sum(1 for r in runs if r["completed"] and r["wall_s"] <= d)
        a, b = mc.wilson(k, trials)
        row["p_within_%gs" % d] = k / trials
        row["p_within_%gs_lo" % d] = a
        row["p_within_%gs_hi" % d] = b
    if done:
        air = [r["air_s"] for r in done]
        row["air_mean_s"] = sum(air) / len(air)
        row["utilisation_mean"] = sum(r["air_s"] / r["wall_s"] for r in done if r["wall_s"] > 0) / len(done)
        if link.duty < 1.0:
            side = sum(r["side_air_max_s"] for r in done) / len(done)
            row["duty_budget_hours"] = side / (link.duty * 3600.0)
    return row


def added_latency_rows(p, trials=TRIALS):
    """Added latency per authenticated command after the handshake: mean time
    to deliver the protected command minus the unprotected one (same seeds)."""
    rows = []
    for lk in LINKS:
        link = build_link(lk, p)
        base = [("A", "command", command_base_bytes(p))]
        for protocol, variant in configs():
            if variant not in ("hybrid", "per_message"):
                continue  # overhead per command does not depend on the key exchange variant
            fl = [("A", "command", int(command_base_bytes(p) + command_overhead(protocol, variant, p)))]
            for loss in LOSSES:
                n = 1 if loss == 0.0 else trials
                d = []
                for i in range(n):
                    a = run_once(link, fl, loss, SEED + i, p)
                    b = run_once(link, base, loss, SEED + i, p)
                    if a["completed"] and b["completed"]:
                        d.append(a["wall_s"] - b["wall_s"])
                s = mc.summarise(d) if len(d) > 1 else {"mean": d[0] if d else float("nan"),
                                                        "ci_lo": d[0] if d else float("nan"),
                                                        "ci_hi": d[0] if d else float("nan")}
                rows.append({"label": LABEL, "link": lk, "protocol": protocol,
                             "overhead_bytes": command_overhead(protocol, variant, p), "loss": loss,
                             "trials": trials, "deterministic": loss == 0.0, "seed_first": SEED,
                             "added_mean_s": s["mean"], "added_ci_lo": s["ci_lo"], "added_ci_hi": s["ci_hi"]})
    return rows


def ranking_flips(rows, scenario="ttfam"):
    """For each link, the order of configurations by mean wall time at each
    loss, compared with the order at zero loss. Returns a row for every pair
    whose order differs, with whether the 95 percent intervals overlap (an
    overlapping flip is not resolved by the trials)."""
    out = []
    for lk in LINKS:
        sel = [r for r in rows if r["scenario"] == scenario and r["link"] == lk]
        rowmap = {(r["loss"], r["protocol"] + "/" + r["variant"]): r for r in sel}
        def order(loss):
            c = [r for r in sel if r["loss"] == loss]
            c = [r for r in c if r["wall_mean"] == r["wall_mean"]]
            return [(r["protocol"] + "/" + r["variant"]) for r in sorted(c, key=lambda r: r["wall_mean"])]
        base = order(0.0)
        for loss in LOSSES[1:]:
            o = order(loss)
            pos0 = {k: i for i, k in enumerate(base)}
            for i in range(len(o)):
                for j in range(i + 1, len(o)):
                    if o[i] in pos0 and o[j] in pos0 and pos0[o[i]] > pos0[o[j]]:
                        ri, rj = rowmap[(loss, o[i])], rowmap[(loss, o[j])]
                        overlap = not (ri["wall_ci_hi"] < rj["wall_ci_lo"])
                        out.append({"label": LABEL, "scenario": scenario, "link": lk, "loss": loss,
                                    "now_faster": o[i], "now_slower": o[j],
                                    "order_at_zero_loss": "%s before %s" % (o[j], o[i]),
                                    "intervals_overlap": overlap})
            missing = [k for k in base if k not in o]
            for k in missing:
                out.append({"label": LABEL, "scenario": scenario, "link": lk, "loss": loss,
                            "now_faster": "", "now_slower": k,
                            "order_at_zero_loss": "%s no longer completes in any trial" % k})
    return out


# Variance based sensitivity of time to first authenticated message.
SOBOL_INPUTS = [
    ("loss", 0.0, 0.2),
    ("proto_cert_overhead_bytes", 100.0, 400.0),
    ("proto_dtls_handshake_framing_bytes", 60.0, 240.0),
    ("proto_coap_header_bytes", 4.0, 16.0),
    ("turnaround_s", 0.01, 0.1),
    ("rto_factor", 1.5, 4.0),
    ("sr_window_frames", 4.0, 32.0),
]
SOBOL_N = 128
SOBOL_CASES = [("ieee802154", "dtls13", "hybrid"), ("ieee802154", "edhoc_oscore", "hybrid"),
               ("lora_dr5", "dtls13", "hybrid"), ("lora_dr5", "edhoc_oscore", "hybrid")]


def _sobol_eval(args):
    lk, protocol, variant, X, p0 = args
    out = []
    for i, x in enumerate(X):
        p = dict(p0)
        loss = 0.0
        for (name, _, _), v in zip(SOBOL_INPUTS, x):
            if name == "loss":
                loss = float(v)
            elif name == "sr_window_frames":
                p[name] = float(int(round(v)))
            else:
                p[name] = float(v)
        link = build_link(lk, p)
        # Common random numbers: the same seed for every sample, so the output is a
        # deterministic function of the inputs and seed noise does not enter the indices.
        r = run_once(link, scenario_flights("ttfam", protocol, variant, p), loss, SEED, p)
        out.append(r["wall_s"] if r["completed"] else float("nan"))
    return out


def sobol(p, n=SOBOL_N, pool=None):
    """Saltelli sample (SALib 1.6, deterministic Sobol sequence), one seeded run per sample (seed SEED + index),
    Sobol first and total order indices with SALib's bootstrap intervals.
    Also returns the fraction of samples where DTLS 1.3 is faster than EDHOC
    on the same inputs (ranking flip measure)."""
    import numpy as np
    from SALib.sample import saltelli
    from SALib.analyze import sobol as sob
    problem = {"num_vars": len(SOBOL_INPUTS), "names": [s[0] for s in SOBOL_INPUTS],
               "bounds": [[s[1], s[2]] for s in SOBOL_INPUTS]}
    X = saltelli.sample(problem, n, calc_second_order=False)  # Sobol sequence, deterministic
    jobs = [(lk, pr, v, X, p) for lk, pr, v in SOBOL_CASES]
    Ys = (pool.map(_sobol_eval, jobs) if pool else [_sobol_eval(j) for j in jobs])
    rows, flips = [], []
    by = {}
    for (lk, pr, v), Y in zip(SOBOL_CASES, Ys):
        Y = np.array(Y, dtype=float)
        by[(lk, pr)] = Y
        nan = int(np.isnan(Y).sum())
        Yf = np.where(np.isnan(Y), np.nanmax(Y), Y)
        S = sob.analyze(problem, Yf, calc_second_order=False, seed=SEED, print_to_console=False)
        for k, name in enumerate(problem["names"]):
            rows.append({"label": LABEL, "link": lk, "protocol": pr, "variant": v, "input": name,
                         "low": SOBOL_INPUTS[k][1], "high": SOBOL_INPUTS[k][2],
                         "S1": float(S["S1"][k]), "S1_conf": float(S["S1_conf"][k]),
                         "ST": float(S["ST"][k]), "ST_conf": float(S["ST_conf"][k]),
                         "samples": len(Y), "failed_runs_set_to_max": nan, "N": n, "seed": SEED})
    for lk in sorted(set(c[0] for c in SOBOL_CASES)):
        a, b = by[(lk, "dtls13")], by[(lk, "edhoc_oscore")]
        m = ~(np.isnan(a) | np.isnan(b))
        k = int((a[m] < b[m]).sum())
        lo, hi = mc.wilson(k, int(m.sum()))
        flips.append({"label": LABEL, "link": lk, "comparison": "dtls13 hybrid faster than edhoc_oscore hybrid",
                      "samples": int(m.sum()), "count": k, "fraction": k / max(1, int(m.sum())),
                      "fraction_lo": lo, "fraction_hi": hi, "seed": SEED})
    return rows, flips


LORA_OVERHEAD_ALT = 9  # bytes counted by the ns-3 LoRaWAN module (docs/NETSIM_STUDY.md); default stays 13 B


def lorawan_overhead_rows(p):
    """Stated sensitivity: time to first authenticated message on the LoRaWAN links at zero loss with the
    13 B frame overhead of data/shared_inputs.csv against the 9 B of the ns-3 module (deterministic runs)."""
    rows = []
    for lk in ("lora_dr0", "lora_dr5"):
        for protocol, variant in configs():
            res = {}
            for ovh in (p["lorawan_frame_overhead_bytes"], float(LORA_OVERHEAD_ALT)):
                q = dict(p)
                q["lorawan_frame_overhead_bytes"] = ovh
                r = run_once(build_link(lk, q), scenario_flights("ttfam", protocol, variant, q), 0.0, SEED, q)
                res[ovh] = r["wall_s"] if r["completed"] else float("nan")
            a, b = res[p["lorawan_frame_overhead_bytes"]], res[float(LORA_OVERHEAD_ALT)]
            rows.append({"label": LABEL, "link": lk, "protocol": protocol, "variant": variant,
                         "overhead_default_bytes": p["lorawan_frame_overhead_bytes"],
                         "overhead_alt_bytes": float(LORA_OVERHEAD_ALT), "wall_default_s": a, "wall_alt_s": b,
                         "relative_change": (b - a) / a if a == a and a > 0 else float("nan"), "seed": SEED})
    return rows


def write_csv(name, rows, fields=None):
    os.makedirs(RES, exist_ok=True)
    if fields is None:
        fields = []
        for r in rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
    with open(os.path.join(RES, name), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (("%.6g" % r[k]) if isinstance(r.get(k), float) else r.get(k, ""))
                        for k in fields})


def flights_table(p):
    rows = []
    for protocol, variant in configs():
        for sc in ("ttfam", "rekey"):
            for s, lab, b in scenario_flights(sc, protocol, variant, p):
                rows.append({"label": "derived from published", "scenario": sc, "protocol": protocol,
                             "variant": variant, "sender": s, "message": lab, "bytes": b})
    for v in ("classical", "pq_only"):
        for s, lab, b in firmware_flights(v, p):
            rows.append({"label": "derived from published", "scenario": "firmware", "protocol": "any",
                         "variant": v, "sender": s, "message": lab, "bytes": b})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trials", type=int, default=TRIALS)
    ap.add_argument("--sobol-n", type=int, default=SOBOL_N)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2)))
    ap.add_argument("--sobol-only", action="store_true",
                    help="rerun only the sensitivity analysis and keep the other result files")
    a = ap.parse_args(argv)
    t0 = time.time()
    p = model.load_params()
    if a.sobol_only:
        with Pool(a.workers) as pool:
            srows, flips = sobol(p, a.sobol_n, pool)
        write_csv("protocols_sobol.csv", srows)
        write_csv("protocols_sobol_flips.csv", flips)
        print("wrote linksim/results/protocols_sobol*.csv in %.1f s (seed %d)" % (time.time() - t0, SEED))
        return 0
    print("label=%s trials=%d seeds=%d..%d" % (LABEL, a.trials, SEED, SEED + a.trials - 1))
    jobs = []
    for lk in LINKS:
        for protocol, variant in configs():
            for sc in ("ttfam", "rekey"):
                if protocol == "raw_mldsa44" and sc == "rekey":
                    continue
                for loss in LOSSES:
                    jobs.append((sc, lk, protocol, variant, loss, a.trials, p))
        for v in ("classical", "pq_only"):
            for loss in LOSSES:
                jobs.append(("firmware", lk, "any", v, loss, a.trials, p))
    with Pool(a.workers) as pool:
        grid = pool.map(cell, jobs, chunksize=1)
        write_csv("protocols_grid.csv", grid)
        write_csv("protocols_flights.csv", flights_table(p))
        write_csv("protocols_added_latency.csv", added_latency_rows(p, a.trials))
        write_csv("protocols_lorawan_overhead.csv", lorawan_overhead_rows(p))
        write_csv("protocols_rank_flips.csv", ranking_flips(grid),
                  ["label", "scenario", "link", "loss", "now_faster", "now_slower", "order_at_zero_loss",
                   "intervals_overlap"])
        srows, flips = sobol(p, a.sobol_n, pool)
    write_csv("protocols_sobol.csv", srows)
    write_csv("protocols_sobol_flips.csv", flips)
    cfg = [{"key": "label", "value": LABEL}, {"key": "trials_per_cell", "value": a.trials},
           {"key": "seeds", "value": "%d + i for trial i; zero loss cells deterministic" % SEED},
           {"key": "losses", "value": " ".join("%g" % x for x in LOSSES)},
           {"key": "deadlines_s", "value": " ".join("%g" % x for x in DEADLINES_S)},
           {"key": "sobol_N", "value": a.sobol_n}, {"key": "sobol_seed", "value": SEED},
           {"key": "transport", "value": "selective repeat (sim.selective_repeat) for every flight"},
           {"key": "run_seconds", "value": "%.1f" % (time.time() - t0)}]
    write_csv("protocols_config.csv", cfg, ["key", "value"])
    print("wrote linksim/results/protocols_*.csv in %.1f s" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
