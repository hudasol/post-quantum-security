# Glossary (for a reader who is not a cryptographer)

**Authenticity / integrity**: assurance that a message or file really came from the claimed party and was not altered. Different from secrecy.
**Confidentiality / secrecy**: keeping content unreadable to outsiders.
**Public-key cryptography**: schemes with a public key anyone can use and a private key held by one party. RSA, ECDH, ECDSA and Ed25519 are the classical ones; a large quantum computer running Shor's algorithm would break them.
**Symmetric cryptography**: one shared secret key (AES, HMAC, SHA-256). Not broken outright by quantum computers; Grover's algorithm only weakens key strength (I rely on general knowledge here; the retrieved sources I used do not quantify this).
**PQC (post quantum cryptography)**: ordinary algorithms, run on ordinary computers, designed to resist quantum attacks.
**CRQC**: cryptographically relevant quantum computer, one big enough to break today's public key schemes. No date is asserted in this report.
**KEM (key encapsulation mechanism)**: a way for two parties to agree on a shared secret key using public key methods. **ML-KEM (FIPS 203)** is the NIST standard KEM (formerly Kyber); sizes 512/768/1024.
**Digital signature**: a value that proves who produced a message. **ML-DSA (FIPS 204)** (formerly Dilithium; levels 44/65/87) and **SLH-DSA (FIPS 205)** (formerly SPHINCS+) are NIST signature standards. **FN-DSA / FIPS 206** (Falcon) is not yet drafted as of the retrieval date.
**Hash-based signatures**: signatures whose security relies only on hash functions. **LMS/HSS** and **XMSS/XMSS^MT** (NIST SP 800-208; RFC 8554, RFC 8391) are *stateful*; SLH-DSA is *stateless*.
**Stateful**: the signer must remember which one time keys it has used and never use one twice, or forgeries become possible. The state lives with the signer (a build server or hardware security module), not the verifying device.
**HSM**: hardware security module, a tamper resistant box that holds keys and performs signing.
**Hybrid (PQ/T) / dual signature**: combining a classical and a post quantum algorithm so security holds if either survives.
**Crypto-agility**: designing systems so algorithms can be swapped without rebuilding everything (NIST CSWP 39).
**HNDL (harvest now, decrypt later)**: recording encrypted traffic today to decrypt after a quantum computer exists. Applies to secrecy, not to authenticity.
**Mosca inequality**: if how long data must stay secret (X) plus how long migration takes (Y) exceeds the time until a CRQC (Z), you are already late.
**Root of trust / boot ROM / OTP**: the first code and key a chip trusts; stored in mask ROM or one time programmable fuses, so it usually cannot be changed after manufacture.
**Secure boot**: the chip refuses to run firmware whose signature does not verify.
**OTA / SUIT / Uptane**: over the air firmware update; SUIT (IETF) and Uptane are update security frameworks and manifest formats.
**COSE / X.509 / CMS**: formats for carrying signatures and keys; each has registered identifiers for LMS and ML-DSA.
**MAVLink 2 signing**: a 13 B trailer on drone messages holding a link ID, timestamp and a truncated 48 bit tag from a shared 32 B key.
**PX4 / ArduPilot**: the two main open source flight controller firmwares.
**ROS 2 / SROS2 / DDS-Security**: robot middleware and its security layer; DDS-Security specifies RSA/ECC-based authentication.
**micro-ROS**: ROS 2 for microcontrollers.
**Cortex-M4F / M33 / M7 / M0+**: Arm microcontroller cores. M4F has hardware floating point; M33 adds Armv8-M features and TrustZone; M7 is faster; M0+ is the smallest and lacks the DWT cycle counter.
**DWT CYCCNT**: a 32 bit hardware counter of CPU cycles on M3/M4/M33/M7, used for timing.
**pqm4**: a benchmarking framework and results for PQC on Cortex-M4 (to be archived read only in or after January 2027).
**mlkem native / mldsa native**: maintained portable C libraries for ML-KEM and ML-DSA; used by the benchmark plan.
**Stack / flash / RAM**: stack = temporary working memory during a call; flash = program storage; RAM = data memory. Often the limiting resource.
**Cycles**: processor clock ticks; time = cycles / clock frequency.
**Masking**: a defensive technique that splits secret values into random shares so single measurements of power or timing reveal nothing; it multiplies cost.
**Side-channel / fault attack**: attacks on an implementation's physical behaviour (timing, power, glitches) rather than the maths. This report covers only the defensive concept.
**Evidence labels**: *published* (from a retrieved source), *host measured* (run on a PC/server in the work environment, not an MCU), *derived/estimated* (my arithmetic), *inference* (my reasoning).
