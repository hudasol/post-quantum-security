"""Write docs/FORMAL_VERIFICATION.md from formal/results/proverif_results.csv.

Author: Huda Mueen.

Run from the repository root:  python3 -m formal.make_doc
Every result, time and version in the document is read from the results file.
"""
import csv
import os

from formal import build_models

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSV_PATH = os.path.join(HERE, "results", "proverif_results.csv")
DOC = os.path.join(ROOT, "docs", "FORMAL_VERIFICATION.md")

PLAIN = {
    ("session", "S1"): "Nobody but the ground station and the vehicle learns the session signing key that the vehicle "
                       "accepts.",
    ("session", "S2"): "Nobody but the vehicle and the ground station learns the session signing key that the ground "
                       "station accepts.",
    ("session", "S3"): "The same as S1 for the key that replaces the session key at a rekey.",
    ("session", "S4"): "The same as S2 for the key that replaces the session key at a rekey.",
    ("session", "A1"): "When the vehicle accepts a session, the genuine ground station ran that same handshake and "
                       "holds the same key, and each vehicle session matches a distinct ground station session.",
    ("session", "A2"): "When the ground station accepts a session, the genuine vehicle ran that same handshake, and "
                       "each ground station session matches a distinct vehicle session.",
    ("session", "C1"): "The vehicle accepts a command in a session only if the ground station sent that command in "
                       "that session, and accepts it at most once.",
    ("session", "C2"): "A command recorded in one session (before a rekey, or before a link outage and the teardown "
                       "that follows it) is never accepted in another session.",
    ("fallback", "C1"): "With provisioned keys, the vehicle accepts each command only if the ground station sent it, "
                        "and at most once, also across power cycles and new sessions.",
    ("fallback", "C2"): "With provisioned keys and the design change, a command is accepted only in the session in "
                        "which it was sent.",
    ("fallback", "S1"): "The per session key derived from the provisioned key stays secret.",
    ("fallback", "FS"): "Keys of earlier sessions stay secret even if the provisioned key is stolen later.",
    ("firmware", "D1"): "After a device has booted an image of some version, it never boots an image released with "
                        "a lower version (downgrade rejection), even though the attacker can offer any image ever "
                        "signed.",
    ("timestamp", "C1"): "With the published MAVLink rule (any timestamp greater than the last one, gaps allowed), "
                         "each command is accepted at most once and only if sent in that session.",
    ("replay", "S0"): "Sanity check of the command layer models: the abstract session key is never revealed (true by "
                      "construction, since the key is never sent).",
    ("replay", "S1 to S4"): "The same as S1 to S4 of the session group, for the session with change F1 and a replay "
                            "rule that accepts commands out of order (section 9).",
    ("replay", "C1"): "With the replay rule of the model, the vehicle accepts a command in a session only if the "
                      "ground station sent that command in that session, and accepts it at most once.",
    ("replay", "C2"): "With the replay rule of the model, a command sent in one session is never accepted in another "
                      "session.",
    ("replay", "R1"): "Functional check, not a security property: the vehicle can accept a command whose counter is "
                      "below the highest counter it accepted before. A counterexample is the expected result.",
}


def family(model):
    if model.startswith("fallback"):
        return "fallback"
    if model.startswith("firmware"):
        return "firmware"
    if model == "session_timestamp_rule":
        return "timestamp"
    if model.startswith("session_replay"):
        return "replay"
    return "session"


def load():
    return list(csv.DictReader(open(CSV_PATH)))


def get(rows, model, pid):
    for r in rows:
        if r["model"] == model and r["property_id"] == pid:
            return r["result"]
    return "not run"


def weak_form(rows, model, pid):
    for r in rows:
        if r["model"] == model and r["property_id"] == pid:
            return r["weaker_form"] or "none reported"
    return "not run"


def model_time(rows, model):
    for r in rows:
        if r["model"] == model:
            return r["run_time_s_host_measured"]
    return "n/a"


def build(rows):
    version = sorted({r["proverif_version"] for r in rows})
    models = sorted({r["model"] for r in rows})
    n = len(rows)
    n_proved = sum(r["result"] == "proved" for r in rows)
    n_cex = sum(r["result"] == "counterexample" for r in rows)
    n_cbp = sum(r["result"].startswith("cannot be proved") for r in rows)
    L = []
    a = L.append
    a("# Formal verification of the session and update design")
    a("")
    a("Author: Huda Mueen. Generated by `formal/make_doc.py` from `formal/results/proverif_results.csv` "
      "(run `python3 -m formal.run_all`, then `python3 -m formal.make_doc`). Do not edit by hand.")
    a("")
    a("Label of every result in this document: **modelled**. A result is a proof or a counterexample found by "
      f"ProVerif (version {', '.join(version)}, pinned in `formal/install.sh`) for an abstract model of the design. "
      "It is not a test of any implementation, and nothing cryptographic is implemented in this repository.")
    a("")
    a("## 1. What was checked")
    a("")
    a("The models follow `docs/REFERENCE_ARCHITECTURE.md` (sections 1 and 5), the architecture definitions in "
      "`mission/model.py` (architectures B and D) and the rekey assumption of `linksim/protocols.py` (a fresh key "
      "exchange inside the existing session, without signatures). Where the architecture text is silent, the model "
      "states the choice it makes (section 3). Three parts were modelled:")
    a("")
    a("1. **Command channel (architecture B).** The ground station sends a classical Diffie Hellman share and a "
      "fresh KEM public key; the vehicle answers with its own share and a KEM ciphertext; the ground station signs "
      "the transcript and confirms the key; both derive the session key from the Diffie Hellman secret, the KEM "
      "secret and a hash of the transcript. Commands then carry a MAC tag and a sequence number under that key. A "
      "rekey runs a fresh exchange, with a fresh KEM key, protected by the current key. After a link outage the "
      "session is torn down and a new handshake starts.")
    a("2. **Fallback with provisioned keys (architecture D, session half).** A key loaded over a wire is used as "
      "the signing key in every session.")
    a("3. **Firmware update (architecture D, boot half).** An image and its version are signed with an abstract "
      "stateful hash based signature (LMS) and verified by the bootloader, with and without a monotonic version "
      "counter in protected storage.")
    a("")
    a(f"In total {len(models)} model files and {n} queries were run: {n_proved} proved, {n_cex} counterexamples "
      f"and {n_cbp} that the tool could not prove. The counterexamples include the control rows in which both "
      "components are broken on purpose (section 7), the stated designs before each change (section 6), and the "
      "controls and reachability checks of the replay rules (section 9). The "
      "session and fallback models allow an unbounded number of sessions; the firmware models allow an unbounded "
      "number of devices, each booting three times, with three signed releases. The replay rule models of section 9 "
      "state their own bounds on commands per key.")
    a("")
    a("## 2. Assumptions and what is not modelled")
    a("")
    a("- **Perfect primitives.** Signatures, the Diffie Hellman group, the KEM, the hash, the key derivation and "
      "the MAC are abstract functions that cannot be broken unless a model gives a secret to the attacker on "
      "purpose. The 6 byte truncation of the MAVLink 2 tag is not represented; its forgery probability is a "
      "separate, quantitative question.")
    a("- **Dolev Yao attacker.** The attacker reads, deletes, delays, replays and injects any message on the "
      "link, and runs any number of sessions in parallel with the honest parties.")
    a("- **Broken components.** A broken classical component is modelled by giving every Diffie Hellman exponent "
      "to the attacker; a broken KEM by giving every KEM secret key to the attacker.")
    a("- **Forward secrecy.** Long term keys are given to the attacker in a second phase, after all sessions of "
      "the first phase have ended; the query asks whether keys of the first phase become known.")
    a("- **Not modelled:** timing, clocks and the one minute timestamp window; side channels; implementation bugs; "
      "denial of service and jamming (the attacker can always stop the link, so availability is studied in "
      "`docs/MISSION_STUDY.md`, not here); the 30 s grace period in which the old key stays valid during a rekey; "
      "compromise of a third party identity (one ground station and one vehicle identity); key provisioning and "
      "storage; the state management of the LMS signer; physical access to the protected counter.")
    a("")
    a("## 3. Modelling choices")
    a("")
    a("- **Replay rule.** MAVLink 2 accepts a signed message if its timestamp is greater than the last one on the "
      "same stream (`data/raw/S3_robotics.md`, line 25). ProVerif abstracts state, and with a greater than rule and "
      "gaps it could not prove injective agreement (row `session_timestamp_rule` in section 5; the non injective "
      "form holds). The other models therefore use a stricter rule: the vehicle accepts only the next sequence "
      "number. This is a limit of the abstraction, not a finding about the design; the result for the "
      "published rule is recorded as cannot be proved, not as proved. Rules that accept commands out of order "
      "(a replay cache and a bounded window) are modelled separately in section 9.")
    a("- **Session length.** Each session model of sections 6 and 7 carries one command, a rekey and one command "
      "under the new key, then ends. The replay rule models of section 9 carry several commands per key "
      "(bounds in section 9). A new handshake is a new copy of the process, so outage, teardown and a new session "
      "are covered by the unbounded number of copies.")
    a("- **Ground station key pair for the KEM.** In architecture B the ground station sends the KEM public key "
      "and the vehicle encapsulates (`mission/model.py`, flights of architecture B).")
    a("- **Persisted replay state with provisioned keys.** The cited guidance recommends persisting the timestamp "
      "but notes that stored timestamps often stay at the provisioning value because vehicles are powered off by "
      "pulling the battery (`data/raw/S3_robotics.md`, line 37). The fallback model therefore restarts the replay "
      "state of the vehicle at each power cycle.")
    a("")
    a("## 4. Properties in plain language")
    a("")
    a("| Group | Id | Property |")
    a("|---|---|---|")
    for (fam, pid), text in PLAIN.items():
        a(f"| {fam} | {pid} | {text} |")
    a("")
    a("## 5. Results (modelled)")
    a("")
    a("| Model | Attacker setting | Id | Result | Weaker form | Run time s (host measured) |")
    a("|---|---|---|---|---|---|")
    for r in rows:
        a(f"| {r['model']} | {r['attacker_setting']} | {r['property_id']} | {r['result']} | "
          f"{r['weaker_form'] or ''} | {r['run_time_s_host_measured']} |")
    a("")
    a("_result and weaker form: modelled (ProVerif under the Dolev Yao model with abstract primitives); run "
      "time: host measured, wall clock time of the whole model file on the run host, which holds several queries_")
    a("")
    a("## 6. Design findings and changes")
    a("")
    b0, b1 = "session_b_stated", "session_b_fixed"
    a("### F1. The vehicle is not authenticated to the ground station")
    a("")
    a(f"Stated design: A2 {get(rows, b0, 'A2')}, S2 {get(rows, b0, 'S2')}, S4 {get(rows, b0, 'S4')}; "
      f"A1 {get(rows, b0, 'A1')}, S1 {get(rows, b0, 'S1')}, C1 {get(rows, b0, 'C1')}.")
    a("")
    a("What the tool showed: only the ground station signs, so anyone can answer its first message in place of "
      "the vehicle. The ground station then completes a session and holds a key that it shares with that other "
      "party, not with the vehicle. The vehicle side is unaffected: the vehicle still accepts only sessions signed "
      "by the ground station and only commands the ground station sent. The risk is on the ground side: telemetry "
      "and acknowledgements in such a session do not come from the vehicle.")
    a("")
    a("Change: the vehicle signs the transcript with its own long term key (ML-DSA-44, pinned at the ground "
      "station), both signatures cover both identities, and both sides send a key confirmation tag. After the "
      f"change: A1 {get(rows, b1, 'A1')}, A2 {get(rows, b1, 'A2')}, S1 {get(rows, b1, 'S1')}, "
      f"S2 {get(rows, b1, 'S2')}, S3 {get(rows, b1, 'S3')}, S4 {get(rows, b1, 'S4')}, C1 {get(rows, b1, 'C1')}, "
      f"C2 {get(rows, b1, 'C2')}. Cost: one more signature on the down link and one more verification on the "
      "ground station; the vehicle signs once per handshake.")
    a("")
    a("### F2. Provisioned keys allow replay after a power cycle")
    a("")
    a(f"Stated fallback: C1 {get(rows, 'fallback_d_stated', 'C1')}.")
    a("")
    a("What the tool showed: the same provisioned key signs every session, so a command recorded in one session "
      "carries a valid tag in the next one. When the replay state of the vehicle restarts after a power cycle, the "
      "recorded command is accepted a second time.")
    a("")
    a("Change: at every session start the vehicle sends a fresh nonce, the ground station answers with its own "
      "nonce under a tag of the provisioned key, and both derive the session key from the provisioned key and both "
      "nonces; sequence numbers are then bound to the session. After the change: "
      f"C1 {get(rows, 'fallback_d_fixed', 'C1')}, C2 {get(rows, 'fallback_d_fixed', 'C2')}, "
      f"S1 {get(rows, 'fallback_d_fixed', 'S1')}.")
    a("")
    a(f"Remaining limit (not removable without a key exchange): FS {get(rows, 'fallback_d_fixed_fs_provisioned', 'FS')} "
      "for the provisioned design. Whoever later obtains the provisioned key can recompute the keys of earlier "
      "sessions from the recorded nonces. The architecture already states that a captured vehicle exposes these "
      "keys until they expire; provisioned keys should therefore be short lived and the fallback used only where "
      "B cannot finish.")
    a("")
    a("### F3. Firmware downgrade without a version counter")
    a("")
    a(f"Stated design (signature over image and version, no counter): D1 {get(rows, 'firmware_stated_no_counter', 'D1')}. "
      f"With a counter but an unsigned version: D1 {get(rows, 'firmware_counter_unsigned_version', 'D1')}. "
      f"With a counter and a signed version: D1 {get(rows, 'firmware_fixed_counter', 'D1')}.")
    a("")
    a("What the tool showed: a valid signature only says that the vendor once released the image. Without a "
      "counter, an older signed image is accepted after a newer one. With a counter but a version outside the "
      "signed data, an older image can be offered with a higher claimed version.")
    a("")
    a("Change: the signed data covers the image and its version, and the bootloader keeps a monotonic counter in "
      "protected storage, boots only a version at least equal to the counter and then raises the counter.")
    a("")
    a("The one line goal statement that ProVerif printed for each counterexample is kept in "
      "`formal/results/logs/<model>.txt`.")
    a("")
    a("## 7. Value of the hybrid exchange")
    a("")
    hyb = [("classical component broken", "session_b_fixed_classical_broken"),
           ("KEM component broken", "session_b_fixed_kem_broken"),
           ("both broken (control)", "session_b_fixed_both_broken"),
           ("long term keys stolen later", "session_b_fixed_fs_longterm"),
           ("long term keys stolen later and classical broken", "session_b_fixed_fs_longterm_classical_broken"),
           ("long term keys stolen later and KEM broken", "session_b_fixed_fs_longterm_kem_broken"),
           ("long term keys stolen later and both broken (control)", "session_b_fixed_fs_longterm_both_broken")]
    a("| Setting (design with change F1) | S1 vehicle key | S2 ground key | S3 rekey vehicle | S4 rekey ground |")
    a("|---|---|---|---|---|")
    for label, m in hyb:
        a(f"| {label} | {get(rows, m, 'S1')} | {get(rows, m, 'S2')} | {get(rows, m, 'S3')} | {get(rows, m, 'S4')} |")
    a("")
    a("Reading: the session keys stay secret when either component is broken, and stay secret after both long "
      "term keys are stolen later, also with one component broken, because the key derivation takes both secrets. "
      "Only when both components are broken do the keys become known; the control rows confirm that the models "
      "are not secret by construction. A classical only design (architecture A) is in the position of the control "
      "row once its classical part is broken.")
    a("")
    a("## 8. Text the reference architecture should adopt")
    a("")
    a("1. Session start: \"The vehicle also signs the transcript with its own ML-DSA-44 key, pinned at the ground "
      "station; both signatures cover both identities and the full transcript, and each side sends a key "
      "confirmation tag before it accepts the session.\" (F1)")
    a("2. Key derivation: \"The session key is derived from the X25519 secret, the ML-KEM-768 secret and a hash of "
      "the transcript; a rekey uses a fresh ML-KEM key pair and fresh X25519 shares, protected by the current key.\" "
      "(already implied; proved in section 7)")
    a("3. Fallback: \"Provisioned keys are never used directly as signing keys. At every session start both sides "
      "exchange fresh nonces and derive the session signing key from the provisioned key and both nonces, so that "
      "sequence numbers and timestamps are bound to the session.\" (F2)")
    a("4. Boot: \"The LMS signature covers the image and its version. The bootloader keeps a monotonic version "
      "counter in protected storage, boots only an image whose signed version is at least the counter, and then "
      "raises the counter.\" (F3)")
    a("5. Limits: \"The formal check covers an abstract model only (docs/FORMAL_VERIFICATION.md); it does not "
      "cover timing, side channels, implementation or denial of service.\"")
    a("")
    replay_section(rows, a)
    a("## 10. Reproduce")
    a("")
    a("```")
    a("sh formal/install.sh            # ProVerif pinned version, built outside the repository")
    a("python3 -m formal.build_models")
    a("python3 -m formal.run_all")
    a("python3 -m formal.make_doc")
    a("python3 -m unittest discover -s formal -t .")
    a("```")
    a("")
    return "\n".join(L)


REPLAY_MODELS = ["session_replay_cache", "session_replay_cache_fresh_counters", "session_replay_window",
                 "session_replay_window_no_restriction", "session_replay_cache_table_sequential",
                 "session_replay_cache_table_concurrent", "session_replay_cache_broken_no_check"]


def replay_bounds():
    """Bounds of each replay rule model, read from formal/build_models.py."""
    n, na, nr, w = (build_models.CMDS_PER_KEY, build_models.ABSTRACT_CMDS_PER_KEY,
                    build_models.SEQ_READS_PER_KEY, build_models.WINDOW_W)
    unb = "unbounded"
    full, layer = "full handshake with F1, two keys per session", "command layer only, one key per session"
    return [
        # model, session part, acceptance rule, encoding of seen counters, commands sent per key,
        # command messages read per key at the vehicle
        ("session_replay_cache", full, "replay cache", "restriction (indivisible lookup and insert, never forgets)",
         str(n), unb),
        ("session_replay_cache_fresh_counters", full, "replay cache", "restriction; counters are fresh values",
         unb, unb),
        ("session_replay_window", layer, f"bounded window, W = {w}", "process variables, plus the restriction",
         str(na), str(nr)),
        ("session_replay_window_no_restriction", layer, f"bounded window, W = {w}", "process variables only",
         str(na), str(nr)),
        ("session_replay_cache_table_sequential", layer, "replay cache", "ProVerif table, one message after the other",
         str(na), str(nr)),
        ("session_replay_cache_table_concurrent", full, "replay cache", "ProVerif table, messages in parallel branches",
         str(n), unb),
        ("session_replay_cache_broken_no_check", full, "none (control)", "no check", str(n), unb),
    ]


def replay_section(rows, a):
    n, na, nr, w = (build_models.CMDS_PER_KEY, build_models.ABSTRACT_CMDS_PER_KEY,
                    build_models.SEQ_READS_PER_KEY, build_models.WINDOW_W)
    rc, rf, rw, rn = ("session_replay_cache", "session_replay_cache_fresh_counters", "session_replay_window",
                      "session_replay_window_no_restriction")
    ts, tc, br = ("session_replay_cache_table_sequential", "session_replay_cache_table_concurrent",
                  "session_replay_cache_broken_no_check")
    a("## 9. Replay rules that accept commands out of order")
    a("")
    a("The open design question of `docs/LIMITATIONS_AND_PLAN_R6.md` (item L4) is whether the vehicle may accept "
      "commands out of order. Sections 3 and 6 prove C1 for the strict next sequence rule only, and C1 could not be "
      "proved for the published timestamp rule. The models of this section replace only the rule by which the "
      "vehicle accepts a command. The tool behaviour cited below is taken from the ProVerif 2.05 manual "
      "(`data/raw/proverif_manual_notes.md`).")
    a("")
    a("### 9.1 Encodings")
    a("")
    a("- **Seen counter table as a restriction** (models `session_replay_cache`, `session_replay_cache_fresh_counters`, "
      "`session_replay_window`). Every branch of the vehicle that accepts a command draws a fresh stamp and records "
      "the event Mark(session, counter, stamp). A restriction keeps only the traces in which no two branches record "
      "the same session and counter with different stamps; ProVerif proves the queries on exactly those traces "
      "(manual, section 6.2). A branch that would accept a pair already accepted therefore cannot proceed, which is "
      "the behaviour of a vehicle that looks the pair up in a table of accepted pairs and inserts it in one "
      "indivisible step, with a table that never forgets an entry and is keyed by the session identifier. The "
      "restriction is an assumption about the vehicle, not something the tool proves. What the tool proves under it "
      "is that every accepted command was sent by the ground station in that session (the tag and the session "
      "binding), and, with counters that the sender never repeats under one key, that each sent command is "
      "accepted at most once.")
    a("- **ProVerif tables** (models `session_replay_cache_table_concurrent` and "
      "`session_replay_cache_table_sequential`). The vehicle runs `get seen(=session, =counter) in (drop) else "
      "insert seen(session, counter); accept`. Records cannot be deleted from a table (manual, section 4.1.5), so a "
      "table can express a cache that never forgets but not a window that evicts old counters. In the concurrent "
      "model the vehicle handles command messages in parallel branches, so the lookup and the insert are two steps "
      "that other branches can interleave. In the sequential model the vehicle reads command messages one after "
      "the other.")
    a(f"- **Bounded window** (models `session_replay_window` and `session_replay_window_no_restriction`, W = {w}). "
      "The vehicle reads command messages one after the other and keeps in process variables the highest accepted "
      "counter and the counters accepted so far. It accepts counter t if the tag is valid, t is greater than the "
      "highest accepted counter minus W, and t was not accepted before. Inside the bound on messages the state is "
      "exact, and every counter at or below the highest minus W is rejected by the window test, as in a window that "
      "keeps a bitmap of the last W counters. In `session_replay_window` the seen counter restriction is added to "
      "help the tool; it removes no trace of this process, because the process itself never accepts a counter twice "
      "under one key (a hand argument from the process text, not checked by the tool). "
      "`session_replay_window_no_restriction` is the same rule without that help.")
    a("- **Control** (model `session_replay_cache_broken_no_check`). The vehicle accepts any command with a valid "
      "tag and does not consult a table.")
    a("- **Full handshake or command layer.** The models with parallel acceptance branches keep the whole session "
      "with change F1 (hybrid exchange, both transcript signatures, key confirmation, rekey) and ask the secrecy "
      "queries of section 4 as a sanity check. The models that read messages one after the other exhausted the "
      "memory of the run host inside the full handshake, so they are written on the command layer only, in the "
      "style of `session_timestamp_rule`: each session is a fresh abstract key and a fresh session identifier. Their "
      "secrecy query S0 holds by construction and only checks that the command layer does not send the key.")
    a("- **Commands per key.** The ground station sends several commands per key, with counters starting at 1 under "
      "each key; in `session_replay_cache_fresh_counters` it sends any number of commands per key. In the full "
      "handshake models, commands under the first key are accepted in parallel with the rekey, so an old key "
      "command may still be accepted after the rekey; this is a longer grace period than the 30 s of the "
      "architecture and therefore gives the attacker at least as much room.")
    a("")
    a("### 9.2 Bounds of each model")
    a("")
    a("Every model allows an unbounded number of sessions in parallel. Command messages read at the vehicle include "
      "messages sent by the attacker.")
    a("")
    a("| Model | Session part | Acceptance rule | Encoding of seen counters | Commands sent per key | "
      "Command messages read per key at the vehicle |")
    a("|---|---|---|---|---|---|")
    for row in replay_bounds():
        a("| " + " | ".join(row) + " |")
    a("")
    a("### 9.3 Results (modelled)")
    a("")
    qids = ["S0", "S1", "S2", "S3", "S4", "C1", "C2", "R1"]
    a("| Model | " + " | ".join(qids) + " | C1 weaker form |")
    a("|---|" + "---|" * (len(qids) + 1))
    for m in REPLAY_MODELS:
        cells = [get(rows, m, q) if get(rows, m, q) != "not run" else "not asked" for q in qids]
        a(f"| {m} | " + " | ".join(cells) + f" | {weak_form(rows, m, 'C1')} |")
    a("")
    a("_modelled: ProVerif under the Dolev Yao model with abstract primitives. R1 is a reachability check whose "
      "expected result is a counterexample; run times are in section 5._")
    a("")
    a("### 9.4 Reading")
    a("")
    a(f"- **Replay cache, indivisible lookup and insert.** C1 {get(rows, rc, 'C1')} and C2 {get(rows, rc, 'C2')} "
      f"with {n} commands per key, and C1 {get(rows, rf, 'C1')} and C2 {get(rows, rf, 'C2')} with any number of "
      "commands per key, in the full handshake. The session keys stay secret in the same model "
      f"(S1 {get(rows, rc, 'S1')}, S2 {get(rows, rc, 'S2')}, S3 {get(rows, rc, 'S3')}, S4 {get(rows, rc, 'S4')}), "
      "so adding the rule does not disturb the handshake. In the model, a vehicle may therefore accept commands out "
      "of order and with gaps, provided it remembers every accepted (session, counter) pair for the life of the key "
      "and checks and records a pair in one step.")
    a(f"- **Control without the check.** C1 {get(rows, br, 'C1')} (weaker form: {weak_form(rows, br, 'C1')}): "
      "the attacker delivers a recorded command twice and the vehicle accepts it twice. The proof of the cache "
      "model therefore rests on the table, not on the rest of the model.")
    a(f"- **Tables, lookup and insert in two steps.** C1 {get(rows, tc, 'C1')}: two branches of the vehicle both "
      "find no entry for the same command, both insert it, and both accept it (the goal statement of the trace is in "
      f"`formal/results/logs/{tc}.txt`). A vehicle that checks and records counters on two receive paths at once "
      "(two radios, or a check and a store in different tasks) needs the lookup and the insert to be one "
      "indivisible step.")
    a(f"- **Tables, one message after the other.** C1 {get(rows, ts, 'C1')} (weaker form: "
      f"{weak_form(rows, ts, 'C1')}). The tool ignores how often an action repeats (manual, section 6.2), so the "
      "absence of a table entry is not kept in its abstraction. As for the published timestamp rule in section 3, "
      "this is a limit of the tool, not a finding about the design, and it is recorded as such.")
    a(f"- **Bounded window, W = {w}.** C1 {get(rows, rw, 'C1')} and C2 {get(rows, rw, 'C2')} with the restriction, "
      f"inside the bound of {nr} command messages per key. Without the restriction C1 {get(rows, rn, 'C1')} "
      f"(weaker form: {weak_form(rows, rn, 'C1')}) and C2 {get(rows, rn, 'C2')}, for the same reason as the "
      f"sequential table. R1 {get(rows, rw, 'R1')}: the vehicle does accept a command older than the highest "
      "accepted one, so the model is not the strict rule in disguise.")
    a("")
    a("### 9.5 What these proofs do not say about a real replay window")
    a("")
    a("- A real window forgets counters that fall out of it. The cache models never forget, and the window model "
      "keeps every counter it accepted within its bound on messages. The proof covers a real window only through the "
      "window test, which rejects every counter at or below the highest accepted minus W; a cache that evicts "
      "entries without such a floor is in the position of the control model.")
    a("- Counters are unbounded natural numbers. Finite counter width, wrap around and the 48 bit MAVLink "
      "timestamp field are not represented.")
    a("- The vehicle state is never lost inside a key. A reset of the table while the same key stays in use (a "
      "reboot that keeps the key) is not modelled; in architecture B and in the fallback with change F2 every "
      "reboot starts a new handshake and therefore a new session identifier.")
    a("- The window and sequential table models are bounded in the number of command messages the vehicle reads "
      "per key, attacker messages included, and cover the command layer only; an attack that needs more deliveries "
      "under one key is outside them.")
    a("- The restriction is an assumption that the implementation checks and records a pair in one step and keeps "
      "the table for the life of the key; the tool does not prove it, and the concurrent table model shows what "
      "happens without it.")
    a("- Availability is not covered: a window rejects late commands that a cache would accept, and the cost of "
      "that in lost commands is a question for the mission and flight stack studies, not for this model.")
    a("")


EXPECTED = {
    ("session_b_stated", "A2"): "counterexample", ("session_b_stated", "S2"): "counterexample",
    ("session_b_stated", "A1"): "proved", ("session_b_stated", "S1"): "proved", ("session_b_stated", "C1"): "proved",
    ("session_b_fixed", "A2"): "proved", ("session_b_fixed", "S2"): "proved",
    ("fallback_d_stated", "C1"): "counterexample", ("fallback_d_fixed", "C1"): "proved",
    ("fallback_d_fixed_fs_provisioned", "FS"): "counterexample",
    ("firmware_stated_no_counter", "D1"): "counterexample", ("firmware_fixed_counter", "D1"): "proved",
    ("firmware_counter_unsigned_version", "D1"): "counterexample",
    ("session_b_fixed_classical_broken", "S1"): "proved", ("session_b_fixed_kem_broken", "S1"): "proved",
    ("session_b_fixed_both_broken", "S1"): "counterexample",
    ("session_replay_cache", "C1"): "proved", ("session_replay_cache", "C2"): "proved",
    ("session_replay_cache", "S1"): "proved", ("session_replay_cache", "S2"): "proved",
    ("session_replay_cache", "S3"): "proved", ("session_replay_cache", "S4"): "proved",
    ("session_replay_cache_fresh_counters", "C1"): "proved", ("session_replay_cache_fresh_counters", "C2"): "proved",
    ("session_replay_cache_broken_no_check", "C1"): "counterexample",
    ("session_replay_cache_table_concurrent", "C1"): "counterexample",
    ("session_replay_cache_table_sequential", "C1"): "cannot be proved",
    ("session_replay_window", "C1"): "proved", ("session_replay_window", "C2"): "proved",
    ("session_replay_window", "R1"): "counterexample",
    ("session_replay_window_no_restriction", "C1"): "cannot be proved",
}


def check_prose(rows):
    """The fixed prose of sections 6 and 7 is valid only for these results; stop if a rerun differs."""
    bad = [(m, p, get(rows, m, p)) for (m, p), want in EXPECTED.items() if get(rows, m, p) != want]
    if bad:
        raise SystemExit(f"results differ from the prose of the document, revise make_doc.py: {bad}")


def main():
    rows = load()
    check_prose(rows)
    text = build(rows)
    with open(DOC, "w") as f:
        f.write(text)
    print(f"wrote {DOC}")


if __name__ == "__main__":
    main()
