# Design sketch: a post quantum extension of MAVLink signing

Author: Huda Mueen. **This is a design sketch for discussion. It is not a proposal to MAVLink, PX4, ArduPilot or any other project.** The MAVLink maintainers' stated position, as read on 2026-10-12, is that the project has no post quantum roadmap and does not think it needs one (https://github.com/mavlink/mavlink/issues/2525, closed 2026-06-30). Nothing here asks them to change that. All sizes and times are **estimated from published sizes, not measured**.

## Facts the sketch starts from (retrieved)

- MAVLink 2 signing adds a 13 byte field: link id, timestamp and a 6 byte truncated tag computed with a 32 byte shared secret (`data/raw/S3_robotics.md`, lines 19 to 22, from https://mavlink.io/en/guide/message_signing.html).
- A MAVLink 2 frame carries up to 255 bytes of payload; the file transfer message leaves 239 data bytes per message (`data/raw/S3_robotics.md`, lines 29 and 61).
- Published sizes: ML-KEM-768 public key 1184 B and ciphertext 1088 B; ML-DSA-44 public key 1312 B and signature 2420 B (FIPS 203 and 204, evidence rows S2-0401 and S2-0405).

## Idea

The per message tag does not need to change. A symmetric tag is not broken by Shor's algorithm [inference], so the weak point is how the 32 byte key reaches the vehicle and who authorises it. The sketch replaces only the key distribution step.

1. **Provisioning (offline, ground side).** The vehicle is given a pinned ML-DSA-44 verification key for the ground authority, through a wired link, as the signing guide already requires for the shared secret.
2. **Session start (in band, once).** A hybrid exchange (X25519 plus ML-KEM-768) runs over the existing file transfer or a vendor extension message. The ground station signs the transcript with ML-DSA-44; the vehicle verifies it against the pinned key.
3. **Key derivation.** Both sides derive the 32 byte signing key and a fresh link id from the session secret and the transcript, using a standard key derivation function from a reviewed library. (Not implemented here.)
4. **Session body.** Existing signing is unchanged: 13 byte field, 6 byte tag, timestamp rule.
5. **Rotation.** A new exchange at each arming or after a set number of hours; the vehicle wipes the old key.

## Cost (derived)

Handshake payload with the key provisioned in advance: 4,772 B; about 20 messages at 239 B each (4772 / 239 = 19.97, derived). With the key sent in band: 6,068 B, about 26 messages (derived). Time on specific links is in `docs/link_tables.md` (estimated from published sizes, not measured); on a 57.6 kbps effective link the simulator gives about one second without loss, and on LoRaWAN DR0 the exchange is impractical.

## Open questions (no answers claimed)

- Which message carries the handshake, and whether a vendor extension fits the project's own rules for extensions.
- How the timestamp and replay rule interacts with a key that changes mid flight.
- Whether a flight controller with a Cortex M7 has enough free RAM for the 9 kB handshake working set (see `docs/PLANNER_RULES.md` for how that number is derived).
- Whether a gateway on the companion computer should terminate the exchange, leaving the flight controller untouched. This is the same pattern the planner calls HYBRID.

## Limits

No code was written. No security claim is made. A real design needs review by people who specialise in protocol security.
