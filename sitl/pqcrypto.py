"""ctypes bindings to the pinned host builds of mlkem-native (ML-KEM-768) and mldsa-native (ML-DSA-44).

Research benchmark glue for the software in the loop gateway of round 6; no cryptographic primitive is
implemented here. The shared libraries are built outside the repository by sitl/pqlib/build.sh from the
commits pinned by rtlsim/config.sh. SITL_PQLIB names the folder that holds them.
"""
import ctypes
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIB_DIR = os.environ.get('SITL_PQLIB', os.path.join(os.path.dirname(ROOT), 'third_party', 'sitl6_pqlib'))

MLKEM768_PK = 1184
MLKEM768_SK = 2400
MLKEM768_CT = 1088
MLKEM_SS = 32
MLDSA44_PK = 1312
MLDSA44_SK = 2560
MLDSA44_SIG = 2420

_kem = None
_dsa = None


def available(lib_dir=LIB_DIR):
    return all(os.path.exists(os.path.join(lib_dir, f)) for f in ('libmlkem768.so', 'libmldsa44.so'))


def _load(lib_dir=LIB_DIR):
    global _kem, _dsa
    if _kem is None:
        _kem = ctypes.CDLL(os.path.join(lib_dir, 'libmlkem768.so'))
        _dsa = ctypes.CDLL(os.path.join(lib_dir, 'libmldsa44.so'))
        for f in (_kem.PQCP_MLKEM_NATIVE_MLKEM768_keypair, _kem.PQCP_MLKEM_NATIVE_MLKEM768_enc,
                  _kem.PQCP_MLKEM_NATIVE_MLKEM768_dec, _dsa.PQCP_MLDSA_NATIVE_MLDSA44_keypair,
                  _dsa.PQCP_MLDSA_NATIVE_MLDSA44_signature, _dsa.PQCP_MLDSA_NATIVE_MLDSA44_verify):
            f.restype = ctypes.c_int
    return _kem, _dsa


def _buf(n):
    return ctypes.create_string_buffer(n)


def mlkem768_keypair():
    """Return (encapsulation key, decapsulation key) as bytes."""
    kem, _ = _load()
    pk, sk = _buf(MLKEM768_PK), _buf(MLKEM768_SK)
    if kem.PQCP_MLKEM_NATIVE_MLKEM768_keypair(pk, sk) != 0:
        raise RuntimeError('ML-KEM-768 key generation failed')
    return pk.raw, sk.raw


def mlkem768_enc(pk):
    """Return (ciphertext, shared secret) for an encapsulation key."""
    kem, _ = _load()
    if len(pk) != MLKEM768_PK:
        raise ValueError('encapsulation key length')
    ct, ss = _buf(MLKEM768_CT), _buf(MLKEM_SS)
    if kem.PQCP_MLKEM_NATIVE_MLKEM768_enc(ct, ss, pk) != 0:
        raise ValueError('encapsulation key rejected')
    return ct.raw, ss.raw


def mlkem768_dec(ct, sk):
    kem, _ = _load()
    if len(ct) != MLKEM768_CT:
        raise ValueError('ciphertext length')
    ss = _buf(MLKEM_SS)
    if kem.PQCP_MLKEM_NATIVE_MLKEM768_dec(ss, ct, sk) != 0:
        raise ValueError('decapsulation failed')
    return ss.raw


def mldsa44_keypair():
    """Return (public key, secret key) as bytes."""
    _, dsa = _load()
    pk, sk = _buf(MLDSA44_PK), _buf(MLDSA44_SK)
    if dsa.PQCP_MLDSA_NATIVE_MLDSA44_keypair(pk, sk) != 0:
        raise RuntimeError('ML-DSA-44 key generation failed')
    return pk.raw, sk.raw


def mldsa44_sign(msg, sk, ctx=b''):
    _, dsa = _load()
    sig = _buf(MLDSA44_SIG)
    rc = dsa.PQCP_MLDSA_NATIVE_MLDSA44_signature(sig, msg, ctypes.c_size_t(len(msg)), ctx or None,
                                                   ctypes.c_size_t(len(ctx)), sk)
    if rc != 0:
        raise RuntimeError(f'ML-DSA-44 signing failed ({rc})')
    return sig.raw


def mldsa44_verify(sig, msg, pk, ctx=b''):
    """True when the signature verifies; False otherwise (wrong length included)."""
    _, dsa = _load()
    if len(sig) != MLDSA44_SIG or len(pk) != MLDSA44_PK:
        return False
    rc = dsa.PQCP_MLDSA_NATIVE_MLDSA44_verify(sig, msg, ctypes.c_size_t(len(msg)), ctx or None,
                                                ctypes.c_size_t(len(ctx)), pk)
    return rc == 0
