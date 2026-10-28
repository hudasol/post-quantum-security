"""Session gateways of round 6: executed handshake, per message tag and replay acceptance rules.

RESEARCH BENCHMARK GLUE, NOT FOR USE. The gateway pair calls pinned existing libraries only: the Python package
cryptography (X25519, Ed25519, SHA-256, SHAKE256) and the host builds of mlkem-native (ML-KEM-768) and
mldsa-native (ML-DSA-44) through sitl/pqcrypto.py. No cryptographic primitive is implemented here; secrets
are not wiped and nothing is reviewed for side channels.

Messages of design B with change F1 (formal/models/session_b_fixed.pv) and the same glue as the RTL protocol
benchmark of round 6 (rtlsim/proto/sw/proto_bench.c):
  F1 ground to vehicle: gx (X25519 share, 32 B) || ek (ML-KEM-768 encapsulation key, 1184 B)
  F2 vehicle to ground: gy (32 B) || ct (ML-KEM-768 ciphertext, 1088 B)
  F3 ground to vehicle: sign_G(3 || idG || idV || th) || cG (16 B)
  F4 vehicle to ground: sign_V(4 || idV || idG || th) || cV (16 B)
  th = SHAKE256(label_th || F1 || F2, 32), k = SHAKE256(label_kdf || ss_x25519 || ss_kem || th, 32),
  cG = SHAKE256(k || label_cg || th, 16), cV = SHAKE256(k || label_cv || th, 16),
  id = SHAKE256(label_id || long term public key, 32).
The classical session has no ML-KEM parts and uses Ed25519 signatures (64 B).
Design K (kem_auth, the PROTO_DESIGN_KEM_AUTH section of rtlsim/proto/sw/proto_bench.c): no signatures; each side
holds a static ML-KEM-768 key pair whose encapsulation key is pinned at the other side; three flights:
  F1 ground to vehicle: gx (32 B) || ekE (ground ephemeral ML-KEM-768 encapsulation key, 1184 B) || ctV
     (encapsulation to the vehicle static key, 1088 B)
  F2 vehicle to ground: gy (32 B) || ctE (to ekE, 1088 B) || ctG (to the ground static key, 1088 B) || cV (16 B)
  F3 ground to vehicle: cG (16 B)
  th = SHAKE256(label_th || idG || idV || F1 || F2 without cV, 32),
  k = SHAKE256(label_kdf || ss_x25519 || ssV || ssE || ssG || th, 32), cV and cG as above.
The ground accepts after checking cV and the vehicle after checking cG.
Per message tag: the 13 B MAVLink 2 signing field (link id, 6 B counter in the timestamp field, 6 B tag), with
tag = first 6 B of SHA-256(k || frame || link id || counter), the formula of the MAVLink 2 signing guide.
"""
import hmac
import math

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from . import pqcrypto

LABEL_ID = b'r6 identity'
LABEL_TH = b'r6 transcript'
LABEL_KDF = b'r6 session key'
LABEL_CG = b'r6 confirm ground'
LABEL_CV = b'r6 confirm vehicle'
LABEL_RS = b'r6 resync request'
TAG_FIELD_BYTES = 13
CONFIRM_BYTES = 16
RAW = serialization.Encoding.Raw
RAWPUB = serialization.PublicFormat.Raw


def shake256(data, n):
    h = hashes.Hash(hashes.SHAKE256(n))
    h.update(data)
    return h.finalize()


def sha256(data):
    h = hashes.Hash(hashes.SHA256())
    h.update(data)
    return h.finalize()


def ident(pk):
    return shake256(LABEL_ID + pk, 32)


# ---------------------------------------------------------------- long term keys

class LongTerm:
    """A long term key pair of one side: Ed25519 for the classical session, a static ML-KEM-768 key pair for
    design K (kem_auth, no signatures), ML-DSA-44 otherwise."""

    def __init__(self, design):
        self.design = design
        if design == 'kem_auth':
            self.pk, self._sk = pqcrypto.mlkem768_keypair()
        elif design == 'classical':
            self._sk = ed25519.Ed25519PrivateKey.generate()
            self.pk = self._sk.public_key().public_bytes(RAW, RAWPUB)
        else:
            self.pk, self._sk = pqcrypto.mldsa44_keypair()
        self.id = ident(self.pk)

    def decaps(self, ct):
        """Decapsulation with the static ML-KEM-768 key (design K only)."""
        if self.design != 'kem_auth':
            raise ValueError('no static ML-KEM key')
        return pqcrypto.mlkem768_dec(ct, self._sk)

    def sign(self, m):
        if self.design == 'kem_auth':
            raise ValueError('design K has no signatures')
        if self.design == 'classical':
            return self._sk.sign(m)
        return pqcrypto.mldsa44_sign(m, self._sk)


def verify(design, sig, m, pk):
    if design == 'classical':
        if len(sig) != 64:
            return False
        try:
            ed25519.Ed25519PublicKey.from_public_bytes(pk).verify(sig, m)
            return True
        except Exception:
            return False
    return pqcrypto.mldsa44_verify(sig, m, pk)


def sig_bytes(design):
    return 64 if design == 'classical' else pqcrypto.MLDSA44_SIG


def flight_sizes(design):
    """Bytes of the flights as sent (the same sizes as the RTL benchmark): F1 to F4, or F1 to F3 for design K."""
    if design == 'kem_auth':
        return [KA_F1, KA_F2, CONFIRM_BYTES]
    kem = design == 'hybrid'
    f1 = 32 + (pqcrypto.MLKEM768_PK if kem else 0)
    f2 = 32 + (pqcrypto.MLKEM768_CT if kem else 0)
    f3 = sig_bytes(design) + CONFIRM_BYTES
    return [f1, f2, f3, f3]


def _sign_input(flight, ida, idb, th):
    return bytes([flight]) + ida + idb + th


# ---------------------------------------------------------------- handshake

class GroundHandshake:
    """Ground side of one handshake: start() gives F1, on_f2() gives F3, on_f4() accepts."""

    def __init__(self, design, lt_g, pk_v_pinned):
        self.design = design
        self.lt = lt_g
        self.pk_v = pk_v_pinned
        self.id_v = ident(pk_v_pinned)
        self.key = None
        self.accepted = False

    def start(self):
        self._x = x25519.X25519PrivateKey.generate()
        gx = self._x.public_key().public_bytes(RAW, RAWPUB)
        if self.design == 'hybrid':
            ek, self._dk = pqcrypto.mlkem768_keypair()
            self.f1 = gx + ek
        else:
            self.f1 = gx
        return self.f1

    def on_f2(self, f2):
        """Return F3, or raise ValueError on a malformed F2."""
        if len(f2) != flight_sizes(self.design)[1]:
            raise ValueError('F2 length')
        ssx = self._x.exchange(x25519.X25519PublicKey.from_public_bytes(f2[:32]))
        sskem = pqcrypto.mlkem768_dec(f2[32:], self._dk) if self.design == 'hybrid' else b''
        self.th = shake256(LABEL_TH + self.f1 + f2, 32)
        self.key = shake256(LABEL_KDF + ssx + sskem + self.th, 32)
        sig = self.lt.sign(_sign_input(3, self.lt.id, self.id_v, self.th))
        return sig + shake256(self.key + LABEL_CG + self.th, CONFIRM_BYTES)

    def on_f4(self, f4):
        """Verify the vehicle signature against the pinned key and its confirmation tag; returns a reason or None."""
        n = sig_bytes(self.design)
        if len(f4) != n + CONFIRM_BYTES:
            return 'f4_length'
        if not verify(self.design, f4[:n], _sign_input(4, self.id_v, self.lt.id, self.th), self.pk_v):
            return 'f4_signature'
        if f4[n:] != shake256(self.key + LABEL_CV + self.th, CONFIRM_BYTES):
            return 'f4_confirmation'
        self.accepted = True
        return None


class VehicleHandshake:
    """Vehicle side: on_f1() gives F2, on_f3() verifies the ground and gives F4 (or a reason)."""

    def __init__(self, design, lt_v, pk_g_pinned):
        self.design = design
        self.lt = lt_v
        self.pk_g = pk_g_pinned
        self.id_g = ident(pk_g_pinned)
        self.key = None
        self.accepted = False

    def on_f1(self, f1):
        if len(f1) != flight_sizes(self.design)[0]:
            raise ValueError('F1 length')
        y = x25519.X25519PrivateKey.generate()
        gy = y.public_key().public_bytes(RAW, RAWPUB)
        ssx = y.exchange(x25519.X25519PublicKey.from_public_bytes(f1[:32]))
        if self.design == 'hybrid':
            ct, sskem = pqcrypto.mlkem768_enc(f1[32:])
            f2 = gy + ct
        else:
            sskem = b''
            f2 = gy
        self.th = shake256(LABEL_TH + f1 + f2, 32)
        self.key = shake256(LABEL_KDF + ssx + sskem + self.th, 32)
        return f2

    def on_f3(self, f3):
        """Return (F4, None) when the ground is authenticated, else (None, reason)."""
        n = sig_bytes(self.design)
        if len(f3) != n + CONFIRM_BYTES:
            return None, 'f3_length'
        if not verify(self.design, f3[:n], _sign_input(3, self.id_g, self.lt.id, self.th), self.pk_g):
            return None, 'f3_signature'
        if f3[n:] != shake256(self.key + LABEL_CG + self.th, CONFIRM_BYTES):
            return None, 'f3_confirmation'
        sig = self.lt.sign(_sign_input(4, self.lt.id, self.id_g, self.th))
        self.accepted = True
        return sig + shake256(self.key + LABEL_CV + self.th, CONFIRM_BYTES), None


# ---------------------------------------------------------------- design K (kem_auth)

KA_F1 = 32 + pqcrypto.MLKEM768_PK + pqcrypto.MLKEM768_CT
KA_F2_BODY = 32 + 2 * pqcrypto.MLKEM768_CT
KA_F2 = KA_F2_BODY + CONFIRM_BYTES


def ka_transcript(id_g, id_v, f1, f2_body):
    """Transcript hash of design K: both pinned identities, F1 and F2 without its tag."""
    return shake256(LABEL_TH + id_g + id_v + f1 + f2_body, 32)


def ka_kdf(ssx, ss_v, ss_e, ss_g, th):
    """Session key of design K: X25519 secret, then the ML-KEM secrets of the vehicle static key, the ground
    ephemeral key and the ground static key, then the transcript hash (kdf4 of the RTL benchmark)."""
    return shake256(LABEL_KDF + ssx + ss_v + ss_e + ss_g + th, 32)


def confirm(key, label, th):
    return shake256(key + label + th, CONFIRM_BYTES)


class KemAuthGround:
    """Ground side of design K: start() gives F1; on_f2() checks cV and returns (F3, None) or (None, reason)."""

    def __init__(self, lt_g, pk_v_pinned):
        self.design = 'kem_auth'
        self.lt = lt_g
        self.pk_v = pk_v_pinned
        self.id_v = ident(pk_v_pinned)
        self.key = None
        self.accepted = False

    def start(self):
        self._x = x25519.X25519PrivateKey.generate()
        gx = self._x.public_key().public_bytes(RAW, RAWPUB)
        ek, self._dk = pqcrypto.mlkem768_keypair()
        ct_v, self._ss_v = pqcrypto.mlkem768_enc(self.pk_v)
        self.f1 = gx + ek + ct_v
        return self.f1

    def on_f2(self, f2):
        if len(f2) != KA_F2:
            return None, 'f2_length'
        body, tag = f2[:KA_F2_BODY], f2[KA_F2_BODY:]
        ssx = self._x.exchange(x25519.X25519PublicKey.from_public_bytes(body[:32]))
        ss_e = pqcrypto.mlkem768_dec(body[32:32 + pqcrypto.MLKEM768_CT], self._dk)
        ss_g = self.lt.decaps(body[32 + pqcrypto.MLKEM768_CT:])
        self.th = ka_transcript(self.lt.id, self.id_v, self.f1, body)
        self.key = ka_kdf(ssx, self._ss_v, ss_e, ss_g, self.th)
        if not hmac.compare_digest(tag, confirm(self.key, LABEL_CV, self.th)):
            self.key = None
            return None, 'f2_confirmation'
        self.accepted = True
        return confirm(self.key, LABEL_CG, self.th), None


class KemAuthVehicle:
    """Vehicle side of design K: on_f1() gives F2 (with cV); on_f3() checks cG and returns a reason or None."""

    def __init__(self, lt_v, pk_g_pinned):
        self.design = 'kem_auth'
        self.lt = lt_v
        self.pk_g = pk_g_pinned
        self.id_g = ident(pk_g_pinned)
        self.key = None
        self.accepted = False

    def on_f1(self, f1):
        if len(f1) != KA_F1:
            raise ValueError('F1 length')
        y = x25519.X25519PrivateKey.generate()
        gy = y.public_key().public_bytes(RAW, RAWPUB)
        ssx = y.exchange(x25519.X25519PublicKey.from_public_bytes(f1[:32]))
        ss_v = self.lt.decaps(f1[32 + pqcrypto.MLKEM768_PK:])
        ct_e, ss_e = pqcrypto.mlkem768_enc(f1[32:32 + pqcrypto.MLKEM768_PK])
        ct_g, ss_g = pqcrypto.mlkem768_enc(self.pk_g)
        body = gy + ct_e + ct_g
        self.th = ka_transcript(self.id_g, self.lt.id, f1, body)
        self.key = ka_kdf(ssx, ss_v, ss_e, ss_g, self.th)
        return body + confirm(self.key, LABEL_CV, self.th)

    def on_f3(self, f3):
        if len(f3) != CONFIRM_BYTES:
            return 'f3_length'
        if not hmac.compare_digest(f3, confirm(self.key, LABEL_CG, self.th)):
            return 'f3_confirmation'
        self.accepted = True
        return None


# ---------------------------------------------------------------- per message tag

def tag_field(key, frame, link_id, counter):
    """13 B MAVLink 2 signing field over an unsigned frame: link id, 6 B counter, 6 B tag."""
    ts = int(counter).to_bytes(8, 'little')[:6]
    lid = bytes([link_id & 0xFF])
    return lid + ts + sha256(key + frame + lid + ts)[:6]


def check_field(key, frame, field):
    """Return (tag valid, link id, counter) for a frame and its 13 B field."""
    if len(field) != TAG_FIELD_BYTES:
        return False, None, None
    lid = field[0]
    ts = field[1:7]
    ok = sha256(key + frame + bytes([lid]) + ts)[:6] == field[7:]
    return ok, lid, int.from_bytes(ts + b'\x00\x00', 'little')


def resync_request(key, counter):
    """16 B tag of the control message by which the vehicle gateway asks for a new handshake (strict rule)."""
    c = int(counter).to_bytes(8, 'little', signed=True)
    return shake256(key + LABEL_RS + c, CONFIRM_BYTES)


# ---------------------------------------------------------------- replay acceptance rules

class Acceptor:
    """Replay acceptance of the counters of one stream under one rule.

    published: counter greater than the last accepted one (gaps allowed).
    strict: only the next counter (the last accepted plus one; the first counter of a key is 0).
    cache: any counter not yet seen inside a window of `window` counters below the highest accepted one.
    accept() returns (accepted, reason); reasons of a rejection: late_or_duplicate (published), ahead_of_next or
    behind_next (strict), outside_window or duplicate (cache).
    """

    def __init__(self, rule, window=64):
        if rule not in ('published', 'strict', 'cache'):
            raise ValueError(rule)
        self.rule = rule
        self.window = int(window)
        self.hi = -1
        self.seen = set()
        self.max_seen = -1

    def accept(self, c):
        self.max_seen = max(self.max_seen, c)
        if self.rule == 'published':
            if c > self.hi:
                self.hi = c
                return True, None
            return False, 'late_or_duplicate'
        if self.rule == 'strict':
            if c == self.hi + 1:
                self.hi = c
                return True, None
            return False, 'ahead_of_next' if c > self.hi + 1 else 'behind_next'
        if c <= self.hi - self.window:
            return False, 'outside_window'
        if c in self.seen:
            return False, 'duplicate'
        self.seen.add(c)
        if c > self.hi:
            self.hi = c
            lo = self.hi - self.window
            self.seen = {x for x in self.seen if x > lo}
        return True, None

    def gap(self):
        """True when a counter above the next expected one has been seen (strict rule stall)."""
        return self.max_seen > self.hi + 1


def window_from(value):
    return 64 if value is None or (isinstance(value, float) and math.isnan(value)) else int(value)
