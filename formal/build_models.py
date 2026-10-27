"""Render the ProVerif models of the formal verification study from templates.

Author: Huda Mueen.

Run from the repository root:  python3 -m formal.build_models
Writes formal/models/*.pv. Each model is one design (as stated in
docs/REFERENCE_ARCHITECTURE.md, or with a design change) combined with one
attacker setting (which secrets the attacker is given and when). All
primitives are abstract (perfect cryptography); nothing is implemented.
Every rendered file starts with a comment naming its design and setting.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(HERE, "models")

# ---------------------------------------------------------------- primitives

PRIMITIVES = """
free c: channel.

type key.
type skey.
type pkey.
type expo.
type G.
type kemsk.
type kempk.
type coins.

(* Abstract signature (ML-DSA-44 in the architecture). *)
fun pk(skey): pkey.
fun sign(bitstring, skey): bitstring.
fun verify(bitstring, bitstring, pkey): bool
reduc forall m: bitstring, k: skey; verify(sign(m, k), m, pk(k)) = true.

(* Abstract classical Diffie Hellman group (X25519 in the architecture). *)
const g: G [data].
fun exp(G, expo): G.
equation forall x: expo, y: expo; exp(exp(g, x), y) = exp(exp(g, y), x).

(* Abstract KEM (ML-KEM-768 in the architecture): encapsulation with coins r
   gives a ciphertext and a shared secret; decapsulation with the matching
   secret key returns the same shared secret. *)
fun kpk(kemsk): kempk.
fun kct(kempk, coins): bitstring.
fun kss(kempk, coins): bitstring.
fun decaps(kemsk, bitstring): bitstring
reduc forall sk: kemsk, r: coins; decaps(sk, kct(kpk(sk), r)) = kss(kpk(sk), r).

(* Hash, key derivation over both secrets and the transcript hash, and a MAC
   (the MAVLink 2 signing tag, treated as a perfect MAC). *)
fun h(bitstring): bitstring.
fun kdf(G, bitstring, bitstring): key.
fun mac(bitstring, key): bitstring.

const tF1, tF2, tF3, tF4, tConfG, tConfV, tRk1, tRk2, tCmd: bitstring [data].
const idG, idV: bitstring [data].
"""

# ---------------------------------------------------------------- session model

SESSION_EVENTS = """
event VRun(bitstring).
event GSKey(bitstring, key).
event GSAccept(bitstring, key).
event VAccept(bitstring, key).
event GSRekey(bitstring, key).
event VRekey(bitstring, key).
event Send(bitstring, nat, bitstring).
event Acc(bitstring, nat, bitstring).
"""

SESSION_QUERIES = {
    "S1": ("secrecy of the session key at the vehicle",
           "query s: bitstring, k: key; event(VAccept(s, k)) && attacker(k) ==> false."),
    "S2": ("secrecy of the session key at the ground station",
           "query s: bitstring, k: key; event(GSAccept(s, k)) && attacker(k) ==> false."),
    "S3": ("secrecy of the rekeyed session key at the vehicle",
           "query s: bitstring, k: key; event(VRekey(s, k)) && attacker(k) ==> false."),
    "S4": ("secrecy of the rekeyed session key at the ground station",
           "query s: bitstring, k: key; event(GSRekey(s, k)) && attacker(k) ==> false."),
    "A1": ("vehicle authenticates the ground station (injective agreement on the handshake)",
           "query s: bitstring, k: key; inj-event(VAccept(s, k)) ==> inj-event(GSKey(s, k))."),
    "A2": ("ground station authenticates the vehicle (injective agreement on the handshake)",
           "query s: bitstring, k: key; inj-event(GSAccept(s, k)) ==> inj-event(VRun(s))."),
    "C1": ("injective agreement on each command (accepted at most once, only if sent in that session)",
           "query s: bitstring, t: nat, m: bitstring; inj-event(Acc(s, t, m)) ==> inj-event(Send(s, t, m))."),
    "C2": ("no replay of a command into another session (across rekey, link outage and new handshake)",
           "query s: bitstring, t: nat, m: bitstring; event(Acc(s, t, m)) ==> event(Send(s, t, m))."),
}

SESSION_TEMPLATE = """
(* Ground station: one session = handshake, one command, rekey with a fresh
   KEM, one command under the new key, then teardown (the process ends). *)
let GS(skG: skey, pkV: pkey) =
  new x: expo; new dk: kemsk;
  let gx = exp(g, x) in
  let ek = kpk(dk) in
  @LEAK_GS@
  out(c, (tF1, gx, ek));
  in(c, (=tF2, gy: G, ct: bitstring));
  let tr = (gx, ek, gy, ct) in
  let sid = h(tr) in
  let k = kdf(exp(gy, x), decaps(dk, ct), sid) in
  event GSKey(sid, k);
  out(c, (tF3, sign((tF3, @IDS@ tr), skG), mac((tConfG, sid), k)));
  @GS_CHECK_V@
  event GSAccept(sid, k);
  new m1: bitstring;
  event Send(sid, 1, m1);
  out(c, (tCmd, 1, m1, mac((tCmd, 1, m1), k)));
  new x2: expo; new dk2: kemsk;
  let gx2 = exp(g, x2) in
  let ek2 = kpk(dk2) in
  @LEAK_GS2@
  out(c, (tRk1, gx2, ek2, mac((tRk1, gx2, ek2), k)));
  in(c, (=tRk2, gy2: G, ct2: bitstring, w2: bitstring));
  if w2 = mac((tRk2, gx2, ek2, gy2, ct2), k) then
  let sid2 = h((sid, gx2, ek2, gy2, ct2)) in
  let k2 = kdf(exp(gy2, x2), decaps(dk2, ct2), sid2) in
  event GSRekey(sid2, k2);
  new m2: bitstring;
  event Send(sid2, 2, m2);
  out(c, (tCmd, 2, m2, mac((tCmd, 2, m2), k2))).

(* Vehicle: one session; the replay rule is modelled as acceptance of the next
   sequence number only (1 then 2); teardown ends the process and a new
   handshake is a new copy of the process. *)
let V(pkG: pkey, skV: skey) =
  in(c, (=tF1, gx: G, ek: kempk));
  new y: expo; new r: coins;
  let gy = exp(g, y) in
  let ct = kct(ek, r) in
  @LEAK_V@
  out(c, (tF2, gy, ct));
  let tr = (gx, ek, gy, ct) in
  let sid = h(tr) in
  event VRun(sid);
  let k = kdf(exp(gx, y), kss(ek, r), sid) in
  in(c, (=tF3, sg: bitstring, cg: bitstring));
  if verify(sg, (tF3, @IDS@ tr), pkG) = true then
  if cg = mac((tConfG, sid), k) then
  @V_SIGN@
  event VAccept(sid, k);
  in(c, (=tCmd, t1: nat, m1: bitstring, w1: bitstring));
  if t1 = 1 then
  if w1 = mac((tCmd, t1, m1), k) then
  event Acc(sid, t1, m1);
  in(c, (=tRk1, gx2: G, ek2: kempk, w: bitstring));
  if w = mac((tRk1, gx2, ek2), k) then
  new y2: expo; new r2: coins;
  let gy2 = exp(g, y2) in
  let ct2 = kct(ek2, r2) in
  @LEAK_V2@
  out(c, (tRk2, gy2, ct2, mac((tRk2, gx2, ek2, gy2, ct2), k)));
  let sid2 = h((sid, gx2, ek2, gy2, ct2)) in
  let k2 = kdf(exp(gx2, y2), kss(ek2, r2), sid2) in
  event VRekey(sid2, k2);
  in(c, (=tCmd, t2: nat, m2: bitstring, w3: bitstring));
  if t2 = 2 then
  if w3 = mac((tCmd, t2, m2), k2) then
  event Acc(sid2, t2, m2).

process
  new skG: skey; new skV: skey;
  out(c, pk(skG)); out(c, pk(skV));
  ( (!GS(skG, pk(skV))) | (!V(pk(skG), skV)) @LT_LEAK@ )
"""


def render_session(name, design, setting, sigv, leak_dh, leak_kem, lt_leak, queries):
    t = SESSION_TEMPLATE
    if sigv:
        t = t.replace("@IDS@", "idG, idV,")
        t = t.replace("@GS_CHECK_V@",
                      "in(c, (=tF4, sv: bitstring, cv: bitstring));\n"
                      "  if verify(sv, (tF4, idV, idG, tr), pkV) = true then\n"
                      "  if cv = mac((tConfV, sid), k) then")
        t = t.replace("@V_SIGN@", "out(c, (tF4, sign((tF4, idV, idG, tr), skV), mac((tConfV, sid), k)));")
    else:
        t = t.replace("@IDS@", "")
        t = t.replace("@GS_CHECK_V@", "")
        t = t.replace("@V_SIGN@", "")
    gs, gs2, v, v2 = [], [], [], []
    if leak_dh:
        gs.append("out(c, x);"); gs2.append("out(c, x2);"); v.append("out(c, y);"); v2.append("out(c, y2);")
    if leak_kem:
        gs.append("out(c, dk);"); gs2.append("out(c, dk2);")
    t = t.replace("@LEAK_GS@", " ".join(gs)).replace("@LEAK_GS2@", " ".join(gs2))
    t = t.replace("@LEAK_V@", " ".join(v)).replace("@LEAK_V2@", " ".join(v2))
    t = t.replace("@LT_LEAK@", "| (phase 1; out(c, skG); out(c, skV))" if lt_leak else "")
    q = "\n".join(f"(* {qid}: {SESSION_QUERIES[qid][0]} *)\n{SESSION_QUERIES[qid][1]}" for qid in queries)
    head = (f"(* Model {name}. Generated by formal/build_models.py; do not edit by hand.\n"
            f"   Design: {design}\n   Attacker setting: {setting} *)\n")
    return head + PRIMITIVES + SESSION_EVENTS + "\n" + q + "\n" + t


ALL_SESSION = ["S1", "S2", "S3", "S4", "A1", "A2", "C1", "C2"]
SECRECY = ["S1", "S2", "S3", "S4"]

DESIGN_B0 = ("architecture B as stated: hybrid X25519 plus ML-KEM-768 exchange, ML-DSA-44 transcript "
             "signature from the ground station only, verified against a pinned key; MAVLink 2 signing tag "
             "with a sequence number under the derived key; rekey with fresh shares protected by the session key")
DESIGN_B1 = ("architecture B with design change F1: the vehicle also signs the transcript with its own "
             "pinned ML-DSA-44 key, both signatures bind the two identities, and both sides confirm the key")

SESSION_MODELS = [
    # name, design, setting, sigv, leak_dh, leak_kem, lt_leak, queries
    ("session_b_stated", DESIGN_B0, "Dolev Yao attacker, no secret given", False, False, False, False, ALL_SESSION),
    ("session_b_fixed", DESIGN_B1, "Dolev Yao attacker, no secret given", True, False, False, False, ALL_SESSION),
    ("session_b_fixed_classical_broken", DESIGN_B1,
     "classical component broken: every Diffie Hellman exponent is given to the attacker", True, True, False, False, SECRECY),
    ("session_b_fixed_kem_broken", DESIGN_B1,
     "KEM component broken: every KEM secret key is given to the attacker", True, False, True, False, SECRECY),
    ("session_b_fixed_both_broken", DESIGN_B1,
     "both components broken (control: equivalent to a classical only design whose classical part is broken)",
     True, True, True, False, SECRECY),
    ("session_b_fixed_fs_longterm", DESIGN_B1,
     "forward secrecy: both long term signature keys given to the attacker after the sessions (phase 1)",
     True, False, False, True, SECRECY),
    ("session_b_fixed_fs_longterm_classical_broken", DESIGN_B1,
     "forward secrecy: long term keys given after the sessions, and the classical component broken",
     True, True, False, True, SECRECY),
    ("session_b_fixed_fs_longterm_kem_broken", DESIGN_B1,
     "forward secrecy: long term keys given after the sessions, and the KEM component broken",
     True, False, True, True, SECRECY),
    ("session_b_fixed_fs_longterm_both_broken", DESIGN_B1,
     "forward secrecy control: long term keys given after the sessions, and both components broken",
     True, True, True, True, SECRECY),
    ("session_b_stated_fs_longterm", DESIGN_B0,
     "forward secrecy: the ground station signature key given to the attacker after the sessions (phase 1)",
     False, False, False, True, SECRECY),
]

# ---------------------------------------------------------------- fallback (D) model

FALLBACK_QUERIES = {
    "C1": ("injective agreement on each command (accepted at most once, only if sent)",
           None),
    "C2": ("no replay of a command into another session after a link outage or power cycle", None),
    "S1": ("secrecy of the per session key", None),
    "FS": ("secrecy of earlier session keys after compromise of the provisioned key", None),
}

FALLBACK_STATED = """
(* Model fallback_d_stated. Generated by formal/build_models.py; do not edit by hand.
   Design: architecture D as stated: a provisioned 32 byte key shared by the ground station
   and the vehicle is used directly as the MAVLink 2 signing key in every session; after a
   teardown or power cycle the vehicle's replay state restarts from its stored value, which
   the cited guidance notes often stays at the provisioning value.
   Attacker setting: Dolev Yao attacker, no secret given *)
free c: channel.
type key.
fun mac(bitstring, key): bitstring.
const tCmd: bitstring [data].
event Send(nat, bitstring).
event Acc(nat, bitstring).

(* C1: injective agreement on each command (accepted at most once, only if sent) *)
query t: nat, m: bitstring; inj-event(Acc(t, m)) ==> inj-event(Send(t, m)).

let GS(kp: key) =
  new m1: bitstring; event Send(1, m1); out(c, (tCmd, 1, m1, mac((tCmd, 1, m1), kp)));
  new m2: bitstring; event Send(2, m2); out(c, (tCmd, 2, m2, mac((tCmd, 2, m2), kp))).

let V(kp: key) =
  in(c, (=tCmd, t1: nat, m1: bitstring, w1: bitstring));
  if t1 = 1 then if w1 = mac((tCmd, t1, m1), kp) then event Acc(t1, m1);
  in(c, (=tCmd, t2: nat, m2: bitstring, w2: bitstring));
  if t2 = 2 then if w2 = mac((tCmd, t2, m2), kp) then event Acc(t2, m2).

process
  new kp: key;
  ( (!GS(kp)) | (!V(kp)) )
"""

FALLBACK_FIXED = """
(* Model fallback_d_fixed. Generated by formal/build_models.py; do not edit by hand.
   Design: architecture D with design change F2: at each session start (after every teardown
   or power cycle) the vehicle sends a fresh nonce, the ground station answers with its own
   nonce, and both derive the session signing key from the provisioned key and both nonces;
   the sequence number is therefore bound to the session.
   Attacker setting: @SETTING@ *)
free c: channel.
type key.
fun mac(bitstring, key): bitstring.
fun kdfp(key, bitstring, bitstring): key.
const tCmd, tN1, tN2: bitstring [data].
event Send(bitstring, nat, bitstring).
event Acc(bitstring, nat, bitstring).
event VKey(bitstring, key).

@QUERIES@

let GS(kp: key) =
  in(c, (=tN1, nv: bitstring));
  new ng: bitstring;
  out(c, (tN2, ng, mac((tN2, nv, ng), kp)));
  let sid = (nv, ng) in
  let ks = kdfp(kp, nv, ng) in
  new m1: bitstring; event Send(sid, 1, m1); out(c, (tCmd, 1, m1, mac((tCmd, 1, m1), ks)));
  new m2: bitstring; event Send(sid, 2, m2); out(c, (tCmd, 2, m2, mac((tCmd, 2, m2), ks))).

let V(kp: key) =
  new nv: bitstring;
  out(c, (tN1, nv));
  in(c, (=tN2, ng: bitstring, w0: bitstring));
  if w0 = mac((tN2, nv, ng), kp) then
  let sid = (nv, ng) in
  let ks = kdfp(kp, nv, ng) in
  event VKey(sid, ks);
  in(c, (=tCmd, t1: nat, m1: bitstring, w1: bitstring));
  if t1 = 1 then if w1 = mac((tCmd, t1, m1), ks) then event Acc(sid, t1, m1);
  in(c, (=tCmd, t2: nat, m2: bitstring, w2: bitstring));
  if t2 = 2 then if w2 = mac((tCmd, t2, m2), ks) then event Acc(sid, t2, m2).

process
  new kp: key;
  ( (!GS(kp)) | (!V(kp)) @LEAK@ )
"""

FALLBACK_FIXED_QUERIES = [
    ("C1", "query s: bitstring, t: nat, m: bitstring; inj-event(Acc(s, t, m)) ==> inj-event(Send(s, t, m))."),
    ("C2", "query s: bitstring, t: nat, m: bitstring; event(Acc(s, t, m)) ==> event(Send(s, t, m))."),
    ("S1", "query s: bitstring, k: key; event(VKey(s, k)) && attacker(k) ==> false."),
]


def render_fallback_fixed(fs):
    if fs:
        qs = [("FS", "query s: bitstring, k: key; event(VKey(s, k)) && attacker(k) ==> false.")]
        setting = "forward secrecy: the provisioned key is given to the attacker after the sessions (phase 1)"
        leak = "| (phase 1; out(c, kp))"
    else:
        qs = FALLBACK_FIXED_QUERIES
        setting = "Dolev Yao attacker, no secret given"
        leak = ""
    q = "\n".join(f"(* {qid}: {FALLBACK_QUERIES[qid][0]} *)\n{text}" for qid, text in qs)
    t = FALLBACK_FIXED.replace("@QUERIES@", q).replace("@SETTING@", setting).replace("@LEAK@", leak)
    if fs:
        t = t.replace("Model fallback_d_fixed.", "Model fallback_d_fixed_fs_provisioned.")
    return t

# ---------------------------------------------------------------- firmware model

FIRMWARE_QUERY = ("D1", "a device never boots an image released with a lower version than an image it booted before "
                        "(downgrade rejection)")

FIRMWARE_TEMPLATE = """
(* Model @NAME@. Generated by formal/build_models.py; do not edit by hand.
   Design: @DESIGN@
   Attacker setting: Dolev Yao attacker who controls the update channel and replays any
   image ever released; the signing key and protected storage are not compromised. *)
free c: channel.
type skey.
type pkey.

(* Abstract stateful hash based signature (LMS in the architecture). The signer's
   one time key state is assumed to be handled correctly and is not modelled. *)
fun pk(skey): pkey.
fun sign(bitstring, skey): bitstring.
fun verify(bitstring, bitstring, pkey): bool
reduc forall m: bitstring, k: skey; verify(sign(m, k), m, pk(k)) = true.

(* Ghost record of each release (image, true version), used only to state the property. *)
table released(bitstring, nat).
event Booted(bitstring, nat, nat).

(* D1: downgrade rejection: a device never boots an image released with a lower version than one it booted before *)
query d: bitstring, p: nat, n: nat; event(Booted(d, p, n)) ==> n >= p.

let Vendor(skF: skey) =
  new img1: bitstring; insert released(img1, 1);
  out(c, (img1, 1, sign(@SIGNED1@, skF)));
  new img2: bitstring; insert released(img2, 2);
  out(c, (img2, 2, sign(@SIGNED2@, skF)));
  new img3: bitstring; insert released(img3, 3);
  out(c, (img3, 3, sign(@SIGNED3@, skF))).

(* Third boot, given the highest true version booted so far (ghost) and the counter. *)
let Third(dev: bitstring, pkF: pkey, hprev: nat, ctr: nat) =
  in(c, (i3: bitstring, v3: nat, s3: bitstring));
  if verify(s3, @CHECKED3@, pkF) = true then
  @RULE3@
  get released(=i3, r3) in
  event Booted(dev, hprev, r3).

(* A device boots three times: verify the signature, apply the version rule,
   record the event, update the counter in protected storage. *)
let Device(pkF: pkey) =
  new dev: bitstring;
  in(c, (i1: bitstring, v1: nat, s1: bitstring));
  if verify(s1, @CHECKED1@, pkF) = true then
  @RULE1@
  get released(=i1, r1) in
  event Booted(dev, 0, r1);
  in(c, (i2: bitstring, v2: nat, s2: bitstring));
  if verify(s2, @CHECKED2@, pkF) = true then
  @RULE2@
  get released(=i2, r2) in
  event Booted(dev, r1, r2);
  if r2 > r1 then Third(dev, pkF, r2, v2) else Third(dev, pkF, r1, v2).

process
  new skF: skey;
  out(c, pk(skF));
  ( Vendor(skF) | (!Device(pk(skF))) )
"""

FIRMWARE_MODELS = [
    ("firmware_stated_no_counter",
     "firmware signed with LMS over the image and its version, verified by the bootloader, no "
     "version counter (the architecture text names no counter)", True, "none"),
    ("firmware_fixed_counter",
     "design change F3: LMS signature over the image and its version, and a monotonic version counter in "
     "protected storage; the bootloader boots only if the signed version is at least the counter, then "
     "raises the counter to it", True, "counter"),
    ("firmware_counter_unsigned_version",
     "variant: a monotonic counter, but the signature covers the image only and the version is read from "
     "an unsigned header", False, "counter"),
]


def render_firmware(name, design, signed_version, rule):
    t = FIRMWARE_TEMPLATE.replace("@NAME@", name).replace("@DESIGN@", design)
    for i in (1, 2, 3):
        t = t.replace(f"@SIGNED{i}@", f"(img{i}, {i})" if signed_version else f"img{i}")
        t = t.replace(f"@CHECKED{i}@", f"(i{i}, v{i})" if signed_version else f"i{i}")
    if rule == "counter":
        # Counter starts at 0; after a boot it equals the version just booted (versions only rise).
        t = t.replace("@RULE1@", "if v1 >= 0 then")
        t = t.replace("@RULE2@", "if v2 >= v1 then")
        t = t.replace("@RULE3@", "if v3 >= ctr then")
    else:
        for i in (1, 2, 3):
            t = t.replace(f"@RULE{i}@", "")
    return t

# ---------------------------------------------------------------- MAVLink timestamp rule (tool limit record)

TIMESTAMP_RULE = """
(* Model session_timestamp_rule. Generated by formal/build_models.py; do not edit by hand.
   Design: the MAVLink 2 replay rule as published (accept a timestamp greater than the
   last accepted one, gaps allowed) inside one session key; used to record what the tool
   can and cannot prove about this rule. The other models use the stricter next
   sequence number rule.
   Attacker setting: Dolev Yao attacker, no secret given *)
free c: channel.
type key.
fun mac(bitstring, key): bitstring.
const tCmd: bitstring [data].
event Send(bitstring, nat, bitstring).
event Acc(bitstring, nat, bitstring).

(* C1: injective agreement on each command (accepted at most once, only if sent in that session) *)
query s: bitstring, t: nat, m: bitstring; inj-event(Acc(s, t, m)) ==> inj-event(Send(s, t, m)).

let GS(s: bitstring, k: key) =
  new m1: bitstring; event Send(s, 1, m1); out(c, (tCmd, 1, m1, mac((tCmd, 1, m1), k)));
  new m2: bitstring; event Send(s, 3, m2); out(c, (tCmd, 3, m2, mac((tCmd, 3, m2), k))).

let V(s: bitstring, k: key) =
  in(c, (=tCmd, t1: nat, m1: bitstring, w1: bitstring));
  if t1 > 0 then if w1 = mac((tCmd, t1, m1), k) then event Acc(s, t1, m1);
  in(c, (=tCmd, t2: nat, m2: bitstring, w2: bitstring));
  if t2 > t1 then if w2 = mac((tCmd, t2, m2), k) then event Acc(s, t2, m2).

process
  !(new k: key; new s: bitstring; (GS(s, k) | V(s, k)))
"""


# ---------------------------------------------------------------- replay rules that accept commands out of order

# The models with a full handshake (REPLAY_TEMPLATE) are the session of design change F1
# (session_b_fixed: hybrid exchange, both
# transcript signatures, key confirmation, rekey) with a different command acceptance rule at the
# vehicle. The ground station sends CMDS_PER_KEY commands under the session key, rekeys, and sends
# CMDS_PER_KEY commands under the new key, with counters 1, 2, 3 under each key (the counter starts
# again under a new key, which is safe only because the session identifier changes with the key).
# The vehicle accepts commands under the first key in parallel with the rekey, so a command under
# the old key may still be accepted after the rekey (an unbounded grace period; the attacker is
# therefore at least as strong as with the 30 s grace period of the architecture).

CMDS_PER_KEY = 3
WINDOW_W = 2
# The models in which the vehicle reads command messages one after the other (the bounded window and
# the sequential table) exhausted the memory of the run host (about 7 GB) inside the full handshake,
# already with 2 messages per key. They are therefore written on the command layer only, in the style
# of session_timestamp_rule: each session is a fresh abstract key and a fresh session identifier, and
# the ground station sends ABSTRACT_CMDS_PER_KEY commands under it; the vehicle reads at most
# SEQ_READS_PER_KEY command messages under it.
ABSTRACT_CMDS_PER_KEY = 4
SEQ_READS_PER_KEY = 4

REPLAY_QUERIES = {
    "S1": SESSION_QUERIES["S1"],
    "S2": SESSION_QUERIES["S2"],
    "S3": SESSION_QUERIES["S3"],
    "S4": SESSION_QUERIES["S4"],
    "C1": ("injective agreement on each command (accepted at most once, only if sent in that session)",
           "query s: bitstring, t: nat, m: bitstring; inj-event(Acc(s, t, m)) ==> inj-event(Send(s, t, m))."),
    "C2": ("no replay of a command into another session (across rekey, link outage and new handshake)",
           "query s: bitstring, t: nat, m: bitstring; event(Acc(s, t, m)) ==> event(Send(s, t, m))."),
    "R1": ("reachability check: the vehicle accepts a command whose counter is below the highest counter "
           "accepted before (a counterexample is the expected result and shows the rule accepts out of order)",
           "query s: bitstring, t: nat, hi: nat; event(Late(s, t, hi)) ==> false."),
}
REPLAY_QUERIES_FRESH = {
    "C1": ("injective agreement on each command (accepted at most once, only if sent in that session)",
           "query s: bitstring, t: ctr, m: bitstring; inj-event(Acc(s, t, m)) ==> inj-event(Send(s, t, m))."),
    "C2": ("no replay of a command into another session (across rekey, link outage and new handshake)",
           "query s: bitstring, t: ctr, m: bitstring; event(Acc(s, t, m)) ==> event(Send(s, t, m))."),
}

# Seen counter table as a trace restriction: every accepting branch of the vehicle draws a fresh
# stamp and records Mark(session, counter, stamp) at the moment it accepts; the restriction keeps
# only the traces in which no two accepting branches record the same session and counter. A branch
# that would accept a counter already accepted in its session therefore cannot proceed, which is
# the behaviour of a vehicle that looks the pair up in a table of accepted pairs and inserts it in
# one indivisible step (test and set), with a table that never forgets an entry.
REPLAY_RESTRICTION = ("restriction s: bitstring, t: @CTR@, a: stamp, b: stamp; "
                      "event(Mark(s, t, a)) && event(Mark(s, t, b)) ==> a = b.")

REPLAY_TEMPLATE = """
(* Model @NAME@. Generated by formal/build_models.py; do not edit by hand.
   Design: @DESIGN@
   Attacker setting: Dolev Yao attacker, no secret given *)
@PRIMITIVES@
type stamp.
type ctr.
table seen(bitstring, @CTR@).

event VRun(bitstring).
event GSKey(bitstring, key).
event GSAccept(bitstring, key).
event VAccept(bitstring, key).
event GSRekey(bitstring, key).
event VRekey(bitstring, key).
event Send(bitstring, @CTR@, bitstring).
event Acc(bitstring, @CTR@, bitstring).
event Mark(bitstring, @CTR@, stamp).
event Late(bitstring, nat, nat).

@RESTRICTION@

@QUERIES@

(* Commands sent by the ground station under one key. *)
let GSCmds(sid: bitstring, k: key) =
@GS_CMDS@

(* Command acceptance at the vehicle under one key (the rule under test). *)
@V_CMDS@

(* Ground station: handshake with change F1, commands under the session key, rekey with a fresh
   KEM, commands under the new key. *)
let GS(skG: skey, pkV: pkey) =
  new x: expo; new dk: kemsk;
  let gx = exp(g, x) in
  let ek = kpk(dk) in
  out(c, (tF1, gx, ek));
  in(c, (=tF2, gy: G, ct: bitstring));
  let tr = (gx, ek, gy, ct) in
  let sid = h(tr) in
  let k = kdf(exp(gy, x), decaps(dk, ct), sid) in
  event GSKey(sid, k);
  out(c, (tF3, sign((tF3, idG, idV, tr), skG), mac((tConfG, sid), k)));
  in(c, (=tF4, sv: bitstring, cv: bitstring));
  if verify(sv, (tF4, idV, idG, tr), pkV) = true then
  if cv = mac((tConfV, sid), k) then
  event GSAccept(sid, k);
  @GS_SEQ1@
  new x2: expo; new dk2: kemsk;
  let gx2 = exp(g, x2) in
  let ek2 = kpk(dk2) in
  out(c, (tRk1, gx2, ek2, mac((tRk1, gx2, ek2), k)));
  in(c, (=tRk2, gy2: G, ct2: bitstring, w2: bitstring));
  if w2 = mac((tRk2, gx2, ek2, gy2, ct2), k) then
  let sid2 = h((sid, gx2, ek2, gy2, ct2)) in
  let k2 = kdf(exp(gy2, x2), decaps(dk2, ct2), sid2) in
  event GSRekey(sid2, k2);
  GSCmds(sid2, k2).

(* Vehicle: handshake with change F1; commands under the session key are accepted in parallel
   with the rekey; commands under the new key after it. *)
let V(pkG: pkey, skV: skey) =
  in(c, (=tF1, gx: G, ek: kempk));
  new y: expo; new r: coins;
  let gy = exp(g, y) in
  let ct = kct(ek, r) in
  out(c, (tF2, gy, ct));
  let tr = (gx, ek, gy, ct) in
  let sid = h(tr) in
  event VRun(sid);
  let k = kdf(exp(gx, y), kss(ek, r), sid) in
  in(c, (=tF3, sg: bitstring, cg: bitstring));
  if verify(sg, (tF3, idG, idV, tr), pkG) = true then
  if cg = mac((tConfG, sid), k) then
  out(c, (tF4, sign((tF4, idV, idG, tr), skV), mac((tConfV, sid), k)));
  event VAccept(sid, k);
  ( VCmds(sid, k)
  | in(c, (=tRk1, gx2: G, ek2: kempk, w: bitstring));
    if w = mac((tRk1, gx2, ek2), k) then
    new y2: expo; new r2: coins;
    let gy2 = exp(g, y2) in
    let ct2 = kct(ek2, r2) in
    out(c, (tRk2, gy2, ct2, mac((tRk2, gx2, ek2, gy2, ct2), k)));
    let sid2 = h((sid, gx2, ek2, gy2, ct2)) in
    let k2 = kdf(exp(gx2, y2), kss(ek2, r2), sid2) in
    event VRekey(sid2, k2);
    VCmds(sid2, k2) ).

process
  new skG: skey; new skV: skey;
  out(c, pk(skG)); out(c, pk(skV));
  ( (!GS(skG, pk(skV))) | (!V(pk(skG), skV)) )
"""

# Ground station command blocks: a fixed number of counters, or any number of fresh counters.
def gs_cmds_fixed(n):
    return "\n".join(
        f"  new m{i}: bitstring; event Send(sid, {i}, m{i}); out(c, (tCmd, {i}, m{i}, mac((tCmd, {i}, m{i}), k)))"
        + (";" if i < n else ".") for i in range(1, n + 1))


GS_CMDS_FIXED = gs_cmds_fixed(CMDS_PER_KEY)
GS_CMDS_FRESH = ("  !(new t: ctr; new m: bitstring; event Send(sid, t, m); "
                 "out(c, (tCmd, t, m, mac((tCmd, t, m), k)))).")

V_IN = "in(c, (=tCmd, t: @CTR@, m: bitstring, w: bitstring));\n    if w = mac((tCmd, t, m), k) then\n    "

V_CACHE = ("let VCmds(sid: bitstring, k: key) =\n  !( " + V_IN +
           "new st: stamp; event Mark(sid, t, st);\n    event Acc(sid, t, m) ).")
V_NOCHECK = ("let VCmds(sid: bitstring, k: key) =\n  !( " + V_IN + "event Acc(sid, t, m) ).")
V_TABLE_CONCURRENT = ("let VCmds(sid: bitstring, k: key) =\n  !( " + V_IN +
                      "get seen(=sid, =t) in 0 else\n    insert seen(sid, t);\n    event Acc(sid, t, m) ).")


def v_table_sequential(n):
    """Vehicle that reads n command messages one after the other; a message with a bad tag or a
    counter found in the table is dropped and the vehicle reads the next one."""
    out = []
    for i in range(n, 0, -1):
        name = "VCmds" if i == 1 else f"VCmds{i}"
        nxt = f"VCmds{i + 1}(sid, k)" if i < n else "0"
        out.append(f"let {name}(sid: bitstring, k: key) =\n"
                   f"  in(c, (=tCmd, t: nat, m: bitstring, w: bitstring));\n"
                   f"  if w = mac((tCmd, t, m), k) then\n"
                   f"    (get seen(=sid, =t) in {nxt} else insert seen(sid, t); event Acc(sid, t, m); {nxt})\n"
                   f"  else {nxt}.")
    return "\n\n".join(out)


def v_window(n, w):
    """Vehicle that reads n command messages one after the other and keeps, in process variables,
    the highest accepted counter hi and the counters accepted so far. It accepts counter t if the tag
    is valid, t > 0, t + w > hi (that is, t > hi - w) and t is not among the accepted counters; then
    it raises hi to t if t is higher. The accepted counters are exact for the n messages, so the
    rule forgets nothing inside the model; counters at or below hi - w are rejected by the window
    test, as in a bounded window that keeps a bitmap of the last w counters."""
    out = []
    for i in range(n, 0, -1):
        prev = [f"a{j}" for j in range(1, i)]
        params = ", ".join(["sid: bitstring", "k: key", "hi: nat"] + [f"{a}: nat" for a in prev])
        name = "VWin1" if i == 1 else f"VWin{i}"
        fresh = "".join(f" && t <> {a}" for a in prev)
        if i < n:
            args = ", ".join(["sid", "k", "hi"] + prev)
            skip = f"VWin{i + 1}({args}, 0)"
            up = f"VWin{i + 1}(sid, k, t, {', '.join(prev + ['t'])})"
            keep = f"VWin{i + 1}(sid, k, hi, {', '.join(prev + ['t'])})"
        else:
            skip = up = keep = "0"
        out.append(f"let {name}({params}) =\n"
                   f"  in(c, (=tCmd, t: nat, m: bitstring, w: bitstring));\n"
                   f"  if w = mac((tCmd, t, m), k) && t > 0 && t + {w} > hi{fresh} then\n"
                   f"    (new st: stamp; event Mark(sid, t, st);\n"
                   f"     if t > hi then (event Acc(sid, t, m); {up})\n"
                   f"     else (event Late(sid, t, hi); event Acc(sid, t, m); {keep}))\n"
                   f"  else {skip}.")
    out.append("let VCmds(sid: bitstring, k: key) =\n  VWin1(sid, k, 0).")
    return "\n\n".join(out)


DESIGN_RC = ("design change F1 with a replay cache rule: the vehicle keeps a table of accepted (session, "
             "counter) pairs that never forgets an entry, and accepts a command with a valid tag whose counter is "
             "not in the table, in any order and with gaps; lookup and insert are one indivisible step, encoded as "
             "a trace restriction; " + f"{CMDS_PER_KEY} commands per key, two keys per session, unbounded sessions "
             "and unbounded command messages at the vehicle")
DESIGN_RC_FRESH = ("design change F1 with the replay cache rule of session_replay_cache, and any number of commands "
                   "per key: each counter is a fresh value, which keeps only the property the cache rule uses (the "
                   "sender never repeats a counter under one key) and drops the order of counters; unbounded "
                   "sessions, commands per key and command messages at the vehicle")
DESIGN_RC_BROKEN = ("control for session_replay_cache: the same session, but the vehicle accepts any command with a "
                    f"valid tag and does not consult the table; {CMDS_PER_KEY} commands per key, two keys per "
                    "session, unbounded sessions")
DESIGN_RC_TC = ("replay cache written with ProVerif tables, with the vehicle handling command messages in parallel "
                "branches: lookup (get) and insert are two separate steps; "
                f"{CMDS_PER_KEY} commands per key, two keys per session, unbounded sessions")
DESIGN_RC_TS = ("command layer only (abstract session key, as in session_timestamp_rule): replay cache written "
                "with ProVerif tables, the vehicle reads command messages one after the other and drops a message "
                "whose counter is in the table; "
                f"{ABSTRACT_CMDS_PER_KEY} commands per key, at most {SEQ_READS_PER_KEY} command messages read per key "
                "at the vehicle (attacker messages included), one key per session, unbounded sessions; used to "
                "record what the tool can and cannot prove with this encoding")
DESIGN_RW = (f"command layer only (abstract session key, as in session_timestamp_rule): bounded window rule, "
             f"W = {WINDOW_W}: accept counter t if the tag is valid, t is greater than the highest accepted counter "
             "minus W, and t was not accepted before; the vehicle reads command messages one after the other and "
             "keeps its state in process variables; the seen counter restriction of session_replay_cache is added "
             f"and holds on every trace of this process; {ABSTRACT_CMDS_PER_KEY} commands per key, at most "
             f"{SEQ_READS_PER_KEY} command messages read per key at the vehicle (attacker messages included), one key "
             "per session, unbounded sessions")
DESIGN_RW_NR = ("command layer only: the bounded window model session_replay_window without the seen counter restriction (the rule "
                "is the same; only the help given to the tool is removed); "
                f"{ABSTRACT_CMDS_PER_KEY} commands per key, at most {SEQ_READS_PER_KEY} command messages read per key, "
                "one key per session, unbounded sessions; used to record what the tool can and cannot prove")

ABSTRACT_REPLAY_TEMPLATE = """
(* Model @NAME@. Generated by formal/build_models.py; do not edit by hand.
   Design: @DESIGN@
   Attacker setting: Dolev Yao attacker, no secret given *)
free c: channel.
type key.
type stamp.
fun mac(bitstring, key): bitstring.
const tCmd: bitstring [data].
table seen(bitstring, nat).
event VKey(bitstring, key).
event Send(bitstring, nat, bitstring).
event Acc(bitstring, nat, bitstring).
event Mark(bitstring, nat, stamp).
event Late(bitstring, nat, nat).

@RESTRICTION@

@QUERIES@

(* Commands sent by the ground station under one key. *)
let GSCmds(sid: bitstring, k: key) =
@GS_CMDS@

(* Command acceptance at the vehicle under one key (the rule under test). *)
@V_CMDS@

process
  !(new k: key; new s: bitstring; (GSCmds(s, k) | (event VKey(s, k); VCmds(s, k))))
"""

ABSTRACT_QUERIES = {
    "S0": ("sanity check: the command layer never reveals the abstract session key (the key is never sent, so "
           "this holds by construction; secrecy of the derived keys is shown in the full handshake models)",
           "query s: bitstring, k: key; event(VKey(s, k)) && attacker(k) ==> false."),
}

REPLAY_MODELS = [
    # name, design, vehicle rule, ground station block, counter type, restriction, queries, full handshake
    ("session_replay_cache", DESIGN_RC, V_CACHE, GS_CMDS_FIXED, "nat", True,
     ["S1", "S2", "S3", "S4", "C1", "C2"], True),
    ("session_replay_cache_fresh_counters", DESIGN_RC_FRESH, V_CACHE, GS_CMDS_FRESH, "ctr", True,
     ["S1", "S3", "C1", "C2"], True),
    ("session_replay_cache_broken_no_check", DESIGN_RC_BROKEN, V_NOCHECK, GS_CMDS_FIXED, "nat", False,
     ["S1", "S3", "C1", "C2"], True),
    ("session_replay_cache_table_concurrent", DESIGN_RC_TC, V_TABLE_CONCURRENT, GS_CMDS_FIXED, "nat", False,
     ["S1", "S3", "C1", "C2"], True),
    ("session_replay_cache_table_sequential", DESIGN_RC_TS, v_table_sequential(SEQ_READS_PER_KEY),
     gs_cmds_fixed(ABSTRACT_CMDS_PER_KEY), "nat", False, ["S0", "C1", "C2"], False),
    ("session_replay_window", DESIGN_RW, v_window(SEQ_READS_PER_KEY, WINDOW_W),
     gs_cmds_fixed(ABSTRACT_CMDS_PER_KEY), "nat", True, ["S0", "C1", "C2", "R1"], False),
    ("session_replay_window_no_restriction", DESIGN_RW_NR, v_window(SEQ_READS_PER_KEY, WINDOW_W),
     gs_cmds_fixed(ABSTRACT_CMDS_PER_KEY), "nat", False, ["S0", "C1", "C2", "R1"], False),
]


def render_replay(name, design, vrule, gscmds, ctr, restriction, queries, full=True):
    table = dict(REPLAY_QUERIES)
    table.update(ABSTRACT_QUERIES)
    if ctr == "ctr":
        table.update(REPLAY_QUERIES_FRESH)
    if not full:
        table["C2"] = ("no command is accepted in a session other than the one in which it was sent",
                       REPLAY_QUERIES["C2"][1])
    q = "\n".join(f"(* {qid}: {table[qid][0]} *)\n{table[qid][1]}" for qid in queries)
    rs = ("(* Seen counter table, encoded as a restriction on traces (see formal/build_models.py). *)\n"
          + REPLAY_RESTRICTION) if restriction else "(* No seen counter restriction in this model. *)"
    if ctr == "ctr":
        # Commands under the first key run in parallel with the rest of the ground station.
        gs_seq1 = "(" + GS_CMDS_FRESH.strip().rstrip(".") + ") |"
    else:
        gs_seq1 = gscmds.strip().rstrip(".") + ";"
    t = REPLAY_TEMPLATE if full else ABSTRACT_REPLAY_TEMPLATE
    t = t.replace("@NAME@", name).replace("@DESIGN@", design).replace("@PRIMITIVES@", PRIMITIVES.rstrip())
    t = t.replace("@RESTRICTION@", rs).replace("@QUERIES@", q).replace("@GS_SEQ1@", gs_seq1)
    t = t.replace("@GS_CMDS@", gscmds).replace("@V_CMDS@", vrule)
    t = t.replace("@CTR@", ctr)
    return t


def all_models():
    """Return {name: text} for every model."""
    out = {}
    for name, design, setting, sigv, ldh, lkem, lt, qs in SESSION_MODELS:
        out[name] = render_session(name, design, setting, sigv, ldh, lkem, lt, qs)
    out["fallback_d_stated"] = FALLBACK_STATED
    out["fallback_d_fixed"] = render_fallback_fixed(False)
    out["fallback_d_fixed_fs_provisioned"] = render_fallback_fixed(True)
    for name, design, signed, rule in FIRMWARE_MODELS:
        out[name] = render_firmware(name, design, signed, rule)
    out["session_timestamp_rule"] = TIMESTAMP_RULE
    for name, design, vrule, gscmds, ctr, restriction, qs, full in REPLAY_MODELS:
        out[name] = render_replay(name, design, vrule, gscmds, ctr, restriction, qs, full)
    return out


def query_titles():
    """Return {query id: plain language title} used by the runner and the document."""
    t = {k: v[0] for k, v in SESSION_QUERIES.items()}
    t["FS"] = FALLBACK_QUERIES["FS"][0]
    t[FIRMWARE_QUERY[0]] = FIRMWARE_QUERY[1]
    t["R1"] = REPLAY_QUERIES["R1"][0]
    t["S0"] = ABSTRACT_QUERIES["S0"][0]
    return t


def main():
    os.makedirs(MODELS, exist_ok=True)
    for name, text in all_models().items():
        with open(os.path.join(MODELS, name + ".pv"), "w") as f:
            f.write(text.lstrip("\n"))
    print(f"wrote {len(all_models())} models to formal/models/")


if __name__ == "__main__":
    main()
