"""Command line interface. Author: Huda Mueen.

Example: python -m linksim.cli --scenario firmware --fw-bytes 1000000 --link sik
"""
import argparse

from . import model, sim

SCENARIOS = ["handshake", "handshake-prov", "classical", "tag", "firmware",
             "firmware-pq"]


def fmt_time(s):
    if s < 1:
        return "%.1f ms" % (s * 1000)
    if s < 120:
        return "%.2f s" % s
    if s < 7200:
        return "%.1f min" % (s / 60)
    if s < 172800:
        return "%.2f h" % (s / 3600)
    return "%.1f d" % (s / 86400)


def print_table(title, header, rows):
    widths = [max(len(str(x)) for x in col) for col in zip(header, *rows)]
    print("\n" + title)
    line = "  ".join(str(h).ljust(w) for h, w in zip(header, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(c).ljust(w) for c, w in zip(r, widths)))


def footer():
    print("\n" + model.FOOTER)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Deterministic link simulator "
                                 "(size and timing arithmetic only).")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--link", default="all",
                    choices=["all"] + model.LINK_ORDER)
    ap.add_argument("--scenario", default="handshake", choices=SCENARIOS)
    ap.add_argument("--fw-bytes", type=int, default=1000000)
    ap.add_argument("--loss", type=float, default=0.0,
                    help="per fragment loss probability, 0 to 1")
    ap.add_argument("--proto", default="both", choices=["sw", "sr", "both"])
    ap.add_argument("--signed", action="store_true",
                    help="add the 13 B MAVLink signing field to stream frames")
    ap.add_argument("--ecc", action="store_true", help="halve the SiK rate")
    a = ap.parse_args(argv)
    if not 0.0 <= a.loss < 1.0:
        ap.error("--loss must be in [0, 1)")

    p = model.load_params()
    links = model.build_links(p, a.signed, a.ecc)
    keys = model.LINK_ORDER if a.link == "all" else [a.link]
    protos = ["sw", "sr"] if a.proto == "both" else [a.proto]
    print("scenario=%s seed=%d loss=%.3f signed=%s ecc=%s" %
          (a.scenario, a.seed, a.loss, a.signed, a.ecc))

    if a.scenario == "tag":
        rows = []
        for k in keys:
            L = links[k]
            d13 = model.tag_added_latency_s(L, p, p["mav_sig_field_bytes"])
            d16 = model.tag_added_latency_s(L, p, p["tag_hypothetical_bytes"])
            o16 = model.tag_added_occupancy_s(L, p, p["tag_hypothetical_bytes"])
            rows.append([L.label, fmt_time(d13), fmt_time(d16),
                         "%+.3g ms" % ((d16 - d13) * 1000), fmt_time(o16)])
        print_table("Per message tag overhead (13 B MAVLink field vs "
                    "HYPOTHETICAL 16 B tag)",
                    ["link", "added 13 B", "added 16 B (hypothetical)",
                     "difference", "16 B occupancy incl. duty"], rows)
        footer()
        return 0

    rows = []
    for k in keys:
        for pr in protos:
            if a.scenario in ("handshake", "handshake-prov", "classical"):
                var = {"handshake": "hybrid", "handshake-prov": "hybrid_prov",
                       "classical": "classical"}[a.scenario]
                r = sim.run_handshake(k, var, pr, a.loss, a.seed, p, a.signed,
                                      a.ecc)
            else:
                n = a.fw_bytes + (int(p["pq_image_header_bytes"])
                                  if a.scenario == "firmware-pq" else 0)
                r = sim.run_firmware(k, n, pr, a.loss, a.seed, p, a.signed,
                                     a.ecc)
            rows.append([links[k].label, pr, r.payload_bytes, r.unique_frames,
                         r.retransmissions, fmt_time(r.data_air_s),
                         fmt_time(r.ack_air_s), fmt_time(r.duty_wait_s),
                         fmt_time(r.wall_s), "yes" if r.completed else "NO"])
    print_table("Scenario: %s" % a.scenario,
                ["link", "proto", "payload B", "fragments", "retx",
                 "data air", "ack air", "duty wait", "wall time", "done"], rows)
    footer()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
