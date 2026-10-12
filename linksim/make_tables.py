"""Write docs/link_tables.md from the simulator. Author: Huda Mueen.

Run from the repository root: python -m linksim.make_tables
Every table carries the label: estimated from published sizes, not measured.
"""
import os

from . import model, sensitivity, sim
from .cli import fmt_time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "link_tables.md")
LAB = "_" + model.FOOTER + "_"
SEEDS = (1, 2, 3, 4, 5)


def md(header, rows):
    s = ["| " + " | ".join(header) + " |",
         "|" + "|".join("---" for _ in header) + "|"]
    s += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(s)


def size_table(p):
    x = p["x25519_share_bytes"]
    rows = [
        ["X25519 share", int(x), "S3_robotics.md:157"],
        ["ML-KEM-768 encapsulation key", int(p["mlkem768_ek_bytes"]), "S2-0399"],
        ["ML-KEM-768 ciphertext", int(p["mlkem768_ct_bytes"]), "S2-0401"],
        ["Hybrid initiator share (X25519 + ML-KEM-768 key)",
         int(x + p["mlkem768_ek_bytes"]), "sum"],
        ["Hybrid responder share (X25519 + ML-KEM-768 ciphertext)",
         int(x + p["mlkem768_ct_bytes"]), "sum"],
        ["ML-DSA-44 signature", int(p["mldsa44_sig_bytes"]), "S2-0407"],
        ["ML-DSA-44 public key", int(p["mldsa44_pk_bytes"]), "S2-0406"],
        ["Key confirmation (assumption)", int(p["confirm_bytes"]),
         "ASSUMPTION"],
    ]
    for v, name in (("hybrid", "Handshake total, public key sent"),
                    ("hybrid_prov", "Handshake total, public key provisioned"),
                    ("classical", "Classical baseline (X25519, Ed25519)")):
        fl = model.handshake_flights(p, v)
        rows.append([name, sum(f[2] for f in fl),
                     " + ".join(str(f[2]) for f in fl)])
    rows.append(["MAVLink 2 signing field", int(p["mav_sig_field_bytes"]),
                 "S3_robotics.md:19-20 (1 link ID + 6 timestamp + 6 tag)"])
    rows.append(["Hypothetical symmetric tag", int(p["tag_hypothetical_bytes"]),
                 "HYPOTHETICAL"])
    rows.append(["PQ image header (wolfBoot LMS example)",
                 int(p["pq_image_header_bytes"]), "S3_robotics.md:121"])
    return md(["item", "bytes", "source or formula"], rows)


def frag_table(p, links):
    objs = [("Initiator share", 1216), ("Responder share", 1120),
            ("ML-DSA-44 signature", 2420), ("ML-DSA-44 public key", 1312),
            ("Flight F1", model.handshake_flights(p)[0][2]),
            ("Flight F2 (key sent)", model.handshake_flights(p)[1][2]),
            ("Flight F2 (key provisioned)",
             model.handshake_flights(p, "hybrid_prov")[1][2]),
            ("PQ image header", 5288), ("Firmware 256 kB", 256000),
            ("Firmware 1 MB", 1000000), ("1 MB + PQ header", 1005288)]
    hdr = ["object", "bytes"] + [links[k].label + " (%d B)" % links[k].cap
                                 for k in model.LINK_ORDER]
    rows = [[n, b] + [model.frames_for_bytes(b, links[k].cap)
                      for k in model.LINK_ORDER] for n, b in objs]
    return md(hdr, rows)


def latency_table(p, links):
    rows = []
    for k in model.LINK_ORDER:
        L = links[k]
        d13 = model.tag_added_latency_s(L, p, p["mav_sig_field_bytes"])
        d16 = model.tag_added_latency_s(L, p, p["tag_hypothetical_bytes"])
        rows.append([L.label, "%.0f" % L.rate_bps, fmt_time(d13),
                     fmt_time(d16),
                     fmt_time(model.tag_added_occupancy_s(
                         L, p, p["tag_hypothetical_bytes"]))])
    return md(["link", "rate bit/s", "13 B field", "16 B hypothetical tag",
               "16 B occupancy incl. duty cycle"], rows)


def handshake_table(p, links, variant, loss=0.0):
    rows = []
    for k in model.LINK_ORDER:
        cells = [links[k].label]
        for pr in ("sw", "sr"):
            vals = [sim.run_handshake(k, variant, pr, loss, s, p)
                    for s in (SEEDS if loss else (1,))]
            w = sum(v.wall_s for v in vals) / len(vals)
            cells.append(fmt_time(w))
        r = sim.run_handshake(k, variant, "sr", 0.0, 1, p)
        cells += [r.unique_frames, fmt_time(r.data_air_s)]
        rows.append(cells)
    return md(["link", "wall, stop and wait", "wall, selective repeat",
               "fragments", "data air time"], rows)


def fw_table(p, links, loss):
    rows = []
    for k in model.LINK_ORDER:
        cells = [links[k].label]
        for n in (256000, 1000000, 1005288):
            for pr in ("sw", "sr"):
                seeds = SEEDS[:3] if loss else (1,)
                if k == "lorawan" and loss:
                    seeds = SEEDS[:1]
                w = sum(sim.run_firmware(k, n, pr, loss, s, p).wall_s
                        for s in seeds) / len(seeds)
                cells.append(fmt_time(w))
        rows.append(cells)
    return md(["link", "256 kB sw", "256 kB sr", "1 MB sw", "1 MB sr",
               "1 MB + header sw", "1 MB + header sr"], rows)


BLOCKS = {}


def build():
    p = model.load_params()
    links = model.build_links(p)
    parts = ["# Link tables", "",
             "Author: Huda Mueen. Generated by `python -m linksim.make_tables`."
             " Do not edit by hand.", "", LAB, ""]

    def sec(title, body, key=None):
        parts.extend(["## " + title, "", body, "", LAB, ""])
        if key:
            BLOCKS[key] = body + "\n\n" + LAB

    sec("Message size table", size_table(p), "size")
    sec("Fragmentation table (fragments per object)", frag_table(p, links),
        "frag")
    sec("Added latency per message for a tag (30 B payload, one message)",
        latency_table(p, links), "latency")
    sec("Handshake wall time, public key sent, no loss",
        handshake_table(p, links, "hybrid"), "hs")
    sec("Handshake wall time, public key provisioned, no loss",
        handshake_table(p, links, "hybrid_prov"), "hsprov")
    sec("Handshake wall time, public key sent, 10 percent loss "
        "(mean of 5 seeds)", handshake_table(p, links, "hybrid", 0.10),
        "hsloss")
    sec("Firmware update wall time, no loss", fw_table(p, links, 0.0), "fw")
    sec("Firmware update wall time, 10 percent loss (mean of 3 seeds, "
        "1 seed on LoRaWAN)", fw_table(p, links, 0.10), "fwloss")
    res = sensitivity.run()
    sec("Sensitivity summary", sensitivity.to_markdown(res), "sens")
    return "\n".join(parts)


DOC = os.path.join(ROOT, "docs", "LINK_REFERENCE_DESIGN.md")


def refresh_doc():
    """Replace text between <!-- BEGIN key --> and <!-- END key --> markers."""
    if not os.path.exists(DOC):
        return
    with open(DOC) as fh:
        text = fh.read()
    for key, body in BLOCKS.items():
        b, e = "<!-- BEGIN %s -->" % key, "<!-- END %s -->" % key
        if b in text and e in text:
            head, rest = text.split(b, 1)
            _, tail = rest.split(e, 1)
            text = head + b + "\n\n" + body + "\n\n" + e + tail
    with open(DOC, "w") as fh:
        fh.write(text)
    print("refreshed", DOC)


def main():
    text = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write(text)
    print("wrote", OUT)
    refresh_doc()


if __name__ == "__main__":
    main()
