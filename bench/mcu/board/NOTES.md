# Board notes (secondary sources; none of this was run on hardware)

Specs below come from Zephyr board documentation and the pqm4 README, not from the manufacturers' own pages (st.com and nordicsemi.com were not reachable from the research server). Prices are what seller pages showed on 2026-10-11.

| Board | Core | Why it is in the plan | Watch out |
|---|---|---|---|
| NUCLEO-L4R5ZI | Cortex-M4F | pqm4 default platform; lets you reproduce published pqm4 rows | pqm4's benchmark clock path for this board is 20 MHz in code but the README says 24 MHz |
| NUCLEO-U575ZI-Q | Cortex-M33 (TrustZone, FPU) | first M33 target; no published cycles for this board itself, but ML-DSA keygen and sign cycles exist for the related STM32U5A5 (rows S10C-001 to S10C-036), none for ML-KEM (*correction 2026-10-18*) | pqm4 does not support it; Zephyr page mentions an 8 KB instruction cache giving 0-wait-state flash execution |
| NUCLEO-F439ZI or STM32F4DISCOVERY | Cortex-M4F | cheap cross-checks; wolfSSL published ms figures on F439ZI at 168 MHz | F4DISCOVERY needs a USB-TTL converter on PA2/PA3 for pqm4 |
| Raspberry Pi Pico 2 (RP2350) | Cortex-M33 (or Hazard3) | cheapest M33 (about USD/GBP 4-6) | no on-board debugger (needs a SWD probe); its datasheet lists a DWT with comparators; whether CYCCNT is present was not confirmed in the lines read: run the counter self-check |
| Pixhawk 6C | Cortex-M7 | real flight-controller class | M7 is a different family: never share an axis with M4/M33; DWT needs unlock; only after E1 works |

Do not use Cortex-M0+ boards (RP2040) with this harness: M0+ has no DWT cycle counter; use a hardware timer instead and report it as a different method.
