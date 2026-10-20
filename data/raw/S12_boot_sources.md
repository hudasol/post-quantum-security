# S12 boot and update chain sources

Author: Huda Mueen. Retrieval date: 2026-10-20 unless stated. Values are paraphrased. The scripts in `bootchain/` read these values from `bootchain/inputs.csv` (cited rows) and `energy/retrieved_benchmarks.csv` (hash throughput), and read signature cycles directly from `data/evidence.csv` by id.

## 1. Flight stack image size limits

| Statement | URL | Location |
|---|---|---|
| Early FMUv2 Pixhawk series flight controllers had a hardware issue that limited them to 1 MB of flash; later boards can use the full 2 MB with an updated bootloader (FMUv3 firmware) | https://docs.px4.io/v1.13/zh/config/firmware | section "FMUv2 Bootloader" update |
| Forum reply (JulianOes, 2018-10-06): a silicon erratum on some older STM32F4 chips means only 1 MB can be used safely; the px4fmu-v2 linker script configures 1 MB of flash | https://discuss.px4.io/t/why-doesnt-px4fmu-v2-default-use-2m-flash/8024 | posts of 2018-10-06 and 2018-10-08 |
| Crazyflie 2.1 main MCU has 1 MB flash | https://www.bitcraze.io/documentation/hardware/crazyflie_2_1/crazyflie_2_1-datasheet.pdf | Rev 3, section 3 |

No retrieved page states an actual PX4 or ArduPilot binary size. The scripts therefore treat the image size as an assumption range bounded above by the cited 1 MB and 2 MB flash limits. This is recorded as `unverified` for the size itself.

## 2. Hash throughput

Software and hardware SHA-256 throughput on three Cortex-M4 boards are listed in `data/raw/S12_energy_sources.md` section 2 (Oryx Embedded CycloneCRYPTO 2.5.0 pages). Cycles per byte are derived by the scripts as clock divided by throughput, labelled `derived from published`. No reference manual was retrieved, so the hardware HASH figure comes from these benchmark pages and not from a vendor manual. The 2021/781 paper Table 1 SHA-256 time columns (KTicks) are not used, for the reason recorded in `data/evidence.csv` row S10D-001.

## 3. Published boot and update measurements used for comparison

- wolfBoot total boot time rows S2-0347 to S2-0357 in `data/evidence.csv` (STM32H563 at 320 MHz as recorded, image of about 100 KB, time from reset to a GPIO signal). Boot times are in the notes column; the scripts parse them.
- 2021/781 (supplied PDF, Banegas et al.), Table 8 page 15: relative change of flash, stack and data transfer for SUIT updates (U2 and U3) when Ed25519 with SHA-256 is replaced by Falcon, LMS or Dilithium with SHA3-256; base data transfer 47 kB (U2) and 53 kB (U3). Section 6.2 gives manifest sizes 419 B plus signature (64, 666, 2420 and 4756 B). Tables 5 to 7 give verification times in ms that are already in `data/evidence.csv` (S10D rows).

## 4. Immutable root of trust and hardware only cryptography

Sources already in `data/raw/S4_migration.md`: RFC 9019 (boot code in ROM cannot change; recommends post quantum, for example hash based, signatures for such code), NIST CSWP 39 section 4.5 (functions in an integrated circuit cannot change, so the chip must be replaced if the algorithm must change), the Caliptra example (a software ML-DSA chain added by firmware does not make the ROM rooted classical chain quantum safe), and wolfBoot hybrid and keystore notes. Retrieved on 2026-10-20: the STM32H563 product page lists "ECDSA signature verification" and a HASH accelerator, and the STM32U5A5 page lists a PKA; neither page states whether these blocks support any post quantum algorithm (`unverified`).
