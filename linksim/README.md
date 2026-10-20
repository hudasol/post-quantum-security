# linksim

Author: Huda Mueen

A small deterministic simulator for the cost of a post quantum session start and a per message tag on narrow drone and robot links. It performs size and timing arithmetic only. It implements no cryptographic primitive, generates no keys and performs no hashing. Messages are byte counts.

All outputs are **estimated from published sizes, not measured**.

## Layout

| File | Role |
|---|---|
| `params.csv` | Every input, tagged `cited` (with source row or file and line) or `assumption` |
| `model.py` | Frame and fragment arithmetic, air time, duty cycle silence, tag latency, handshake flights |
| `sim.py` | Seeded `random.Random` simulation: handshake delivery, firmware update, stop and wait, selective repeat |
| `cli.py` | Command line tables |
| `sensitivity.py` | Plus and minus 50 percent on assumptions, loss sweep 0, 1, 5, 10 percent |
| `make_tables.py` | Writes `docs/link_tables.md` and refreshes marked blocks in `docs/LINK_REFERENCE_DESIGN.md` |
| `make_plots.py` | Writes `docs/figures/linksim_handshake.png` |
| `lora.py` | LoRa time on air formula and a LoRaWAN link whose air time follows it (fourth round) |
| `mac802154.py` | IEEE 802.15.4 frame timing with 6LoWPAN fragmentation; each cited cost behind a flag (fourth round) |
| `checks.py` | Closed form checks: duty cycle wait, stop and wait transmissions per fragment |
| `validate_v4.py` | Fourth round validation table, 802.15.4 diagnosis one cause at a time, closed form checks |
| `protocols.py` | Seeded simulation of DTLS 1.3, EDHOC with OSCORE, MAVLink 2 style and DDS Security style profiles |
| `protocols_report.py` | Writes `docs/PROTOCOL_SIM.md` and its figures from the protocol results |
| `tests/` | Unit tests with hand computed cases |

## Usage

Run from the repository root.

```
python -m linksim.cli --scenario handshake --link all --seed 1 --loss 0.05
python -m linksim.cli --scenario handshake-prov --link lorawan
python -m linksim.cli --scenario firmware --fw-bytes 1000000 --link sik --loss 0.1
python -m linksim.cli --scenario firmware-pq --fw-bytes 1000000
python -m linksim.cli --scenario tag
python -m linksim.validate_v4
python -m linksim.protocols --trials 1000
python -m linksim.protocols_report
python -m unittest discover -s linksim/tests -t .
```

Scenarios: `handshake` (public key sent), `handshake-prov` (public key provisioned), `classical` (X25519 and Ed25519 baseline), `tag`, `firmware`, `firmware-pq` (adds the 5288 B header). Options: `--proto sw|sr|both`, `--signed` (adds the 13 B MAVLink signing field to MAVLink framed fragments), `--ecc` (halves the SiK rate as cited).

## Model summary

* Fragments: `ceil(bytes / capacity)`. Capacity is 239 B for MAVLink FTP framed links, 51 B (LoRaWAN EU868 DR0), 81 B (802.15.4), 23 B (BLE).
* Wire bytes add per fragment overhead: 24 B for MAVLink FTP (10 + 2 + 12), 46 B for 802.15.4 (127 minus 81), 4 B for BLE (27 minus 23), 0 B for LoRaWAN (assumption).
* Air time is `8 x wire bytes / rate`. SiK rate is 64 kbps x 0.9 = 57.6 kbps (cited).
* Duty cycle: after a transmission of air time t, that transmitter is silent for t x (1/duty minus 1). Each side has its own budget.
* Stop and wait: one fragment, one acknowledgement. Selective repeat: window of 16 fragments, block acknowledgement bitmap, poll by resending the last fragment.
* Loss: independent Bernoulli per frame, applied to data and acknowledgements alike (assumption).

## Honest limits

See Section 9 of `docs/LINK_REFERENCE_DESIGN.md`. In short: no measurement, no cryptographic computation time, ideal framing for handshake flights, strict duty cycle model, independent loss.
