"""Sensitivity of link ordering and times to assumptions and loss.

Author: Huda Mueen.

Each ASSUMPTION parameter is varied by minus 50 percent and plus 50 percent
(parameters whose base value is zero are probed with one absolute value
listed in PROBES). Loss is swept over 0, 1, 5 and 10 percent. Cited
parameters are not varied. All results are estimated from published sizes,
not measured.
"""
import argparse

from . import model, sim

FW_BYTES = 256000          # smaller image keeps the sweep fast
SEEDS = (1, 2, 3)
LOSS_LEVELS = (0.0, 0.01, 0.05, 0.10)
PROBES = {"frag_hdr_bytes": 4, "lorawan_phy_mac_overhead_bytes": 10}
SKIP = {"kb_bytes", "max_retries", "tag_hypothetical_bytes"}
INT_PARAMS = {"ack_payload_bytes", "sr_window_frames", "confirm_bytes",
              "msg_payload_bytes"}
METRICS = ["hs_sr", "hs_sw", "fw_sr", "fw_sw", "tag16"]


def assumption_names():
    rows = model.load_param_rows()
    return [r["name"] for r in rows
            if r["tag"] == "assumption" and r["name"] not in SKIP]


def metric_table(p, loss=0.0, seeds=SEEDS):
    """{metric: {link: value}} for the parameter dict p."""
    links = model.build_links(p)
    use = (1,) if loss == 0.0 else seeds
    out = {m: {} for m in METRICS}
    for k in model.LINK_ORDER:
        out["hs_sr"][k] = sim.mean_wall(sim.run_handshake, use, link_key=k,
                                        proto="sr", loss=loss, p=p)
        out["hs_sw"][k] = sim.mean_wall(sim.run_handshake, use, link_key=k,
                                        proto="sw", loss=loss, p=p)
        out["fw_sr"][k] = sim.mean_wall(sim.run_firmware, use, link_key=k,
                                        nbytes=FW_BYTES, proto="sr",
                                        loss=loss, p=p)
        out["fw_sw"][k] = sim.mean_wall(sim.run_firmware, use, link_key=k,
                                        nbytes=FW_BYTES, proto="sw",
                                        loss=loss, p=p)
        out["tag16"][k] = model.tag_added_latency_s(
            links[k], p, p["tag_hypothetical_bytes"])
    return out


def ordering(values):
    return tuple(sorted(values, key=lambda k: (values[k], k)))


def variants(name, base):
    if base == 0:
        return [("probe", PROBES[name])]
    lo, hi = base * 0.5, base * 1.5
    if name in INT_PARAMS:
        lo, hi = max(1, round(lo)), round(hi)
    return [("-50%", lo), ("+50%", hi)]


def run(loss_for_params=(0.0, 0.05)):
    base_p = model.load_params()
    result = {"params": [], "loss": [], "base_order": {}}
    base = {l: metric_table(base_p, l) for l in loss_for_params}
    for m in METRICS:
        result["base_order"][m] = ordering(base[0.0][m])
    for name in assumption_names():
        worst = 0.0
        worst_where = ""
        changed = []
        for label, val in variants(name, base_p[name]):
            p = dict(base_p)
            p[name] = float(val)
            for l in loss_for_params:
                if l > 0 and name not in LOSS_RELEVANT:
                    continue
                t = metric_table(p, l)
                for m in METRICS:
                    if m == "tag16" and l > 0:
                        continue
                    if ordering(t[m]) != ordering(base[l][m]):
                        changed.append("%s %s loss %g" % (m, label, l))
                    for k in model.LINK_ORDER:
                        b = base[l][m][k]
                        rel = abs(t[m][k] / b - 1.0) if b else 0.0
                        if rel > worst:
                            worst = rel
                            worst_where = "%s on %s at %s, loss %g" % (
                                m, k, label, l)
        result["params"].append({"name": name, "max_rel_change": worst,
                                 "where": worst_where,
                                 "order_changes": sorted(set(changed))})
    result["params"].sort(key=lambda r: -r["max_rel_change"])
    b0 = metric_table(base_p, 0.0)
    for l in LOSS_LEVELS:
        t = b0 if l == 0.0 else metric_table(base_p, l)
        row = {"loss": l, "order": {m: ordering(t[m]) for m in METRICS},
               "inflation": {}}
        for m in METRICS:
            row["inflation"][m] = {k: t[m][k] / b0[m][k]
                                   for k in model.LINK_ORDER}
        result["loss"].append(row)
    return result


RATE_PARAMS = {"generic_fast_rate_bps", "generic_slow_rate_bps",
               "ble_rate_bps"}
LOSS_RELEVANT = {"rto_factor", "turnaround_s", "turnaround_lorawan_s",
                 "sr_window_frames", "ack_payload_bytes"}


def to_markdown(res):
    lab = {k: v for k, v in zip(model.LINK_ORDER, [
        "SiK", "LoRaWAN", "802.15.4", "BLE", "1 Mbps", "10 kbps"])}
    out = []
    out.append("Base ordering (fastest first) at zero loss:\n")
    out.append("| metric | ordering |\n|---|---|")
    for m in METRICS:
        out.append("| %s | %s |" % (m, " < ".join(lab[k] for k in
                                                   res["base_order"][m])))
    out.append("")
    out.append("Each assumption varied by minus and plus 50 percent "
               "(absolute probe if the base is zero):\n")
    out.append("| assumption | largest relative change | where | ordering "
               "changes |\n|---|---|---|---|")
    for r in res["params"]:
        oc = "none" if not r["order_changes"] else "; ".join(
            r["order_changes"][:3]) + (" ..." if len(r["order_changes"]) > 3
                                       else "")
        out.append("| %s | %.1f%% | %s | %s |" % (
            r["name"], 100 * r["max_rel_change"], r["where"] or "none", oc))
    out.append("")
    out.append("Loss sweep (mean of %d seeds, %d B firmware), ordering "
               "unchanged versus zero loss: " % (len(SEEDS), FW_BYTES))
    base_ord = res["loss"][0]["order"]
    parts = []
    for row in res["loss"][1:]:
        ch = [m for m in METRICS if row["order"][m] != base_ord[m]]
        parts.append("%g%%: %s" % (100 * row["loss"],
                                   "yes" if not ch else "no (" +
                                   ", ".join(ch) + ")"))
    out.append("; ".join(parts) + "\n")
    out.append("| loss | metric | " + " | ".join(lab[k] for k in
                                                 model.LINK_ORDER) + " |")
    out.append("|---|---|" + "---|" * len(model.LINK_ORDER))
    for row in res["loss"][1:]:
        for m in ("hs_sr", "hs_sw", "fw_sr", "fw_sw"):
            out.append("| %g%% | %s time vs no loss | %s |" % (
                100 * row["loss"], m, " | ".join(
                    "x%.2f" % row["inflation"][m][k]
                    for k in model.LINK_ORDER)))
    out.append("")
    out.append("_" + model.FOOTER + "_")
    return "\n".join(out)


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    res = run()
    print(to_markdown(res))
    top = res["params"][0]
    print("\nLargest change overall: %s (%.1f%%, %s)" % (
        top["name"], 100 * top["max_rel_change"], top["where"]))
    proto = [r for r in res["params"] if r["name"] not in RATE_PARAMS][0]
    print("Largest change among non rate assumptions: %s (%.1f%%, %s)" % (
        proto["name"], 100 * proto["max_rel_change"], proto["where"]))
    print("Rate assumptions scale their own link inversely by construction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
