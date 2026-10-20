# S12 Reference board profiles: retrieval log (raw notes)

Author of review: Huda Mueen. Retrieval date for every row: 2026-10-20. Method: web search to locate pages, then web fetch of each page; only pages that returned text are used. No curl, mirror, cache or archive was used. Output: `data/reference_profiles.csv` (label: published for board totals; free budgets would be labelled derived from published).

Unit convention (assumption, recorded in the `arithmetic` column): memory sizes printed as MB or KB are read as binary units (1 MB = 1,048,576 B, 1 KB = 1,024 B). The planner works in kB of 1,000 B, so `planner/profile_study.py` divides bytes by 1,000.

## 1. Retrieved pages

| # | Board or part | URL | Location | What the page states (paraphrase) |
|---|---|---|---|---|
| 1 | Holybro Pixhawk 6X | https://docs.px4.io/v1.15/en/flight_controller/pixhawk6x.html | Introduction | STM32H753, Arm Cortex-M7, up to 480 MHz, 2MB flash, 1MB RAM. No IO processor or flash limit statement in the retrieved text. |
| 2 | Holybro Pixhawk 6X (main branch) | https://docs.px4.io/main/en/flight_controller/pixhawk6x.html | none | Page returned navigation only, no body text. Not used. |
| 3 | Holybro Pixhawk 6C | https://docs.holybro.com/autopilot/pixhawk-6c/technical-specification | FMU Processor; IO Processor | STM32H743, Cortex-M7, 480MHz, 2MB memory (not labelled flash), 1MB SRAM; IO STM32F103, Cortex-M3, 72MHz, 64KB SRAM. |
| 4 | CubePilot Cube Orange | https://docs.px4.io/v1.14/en/flight_controller/cubepilot_cube_orange.html | Key Features; Specifications | STM32H753VI, Cortex-M7, 400 MHz, 2 MB flash described as fully accessible, 1 MB RAM; IO STM32F103, 24 MHz, 8 KB SRAM. |
| 5 | Holybro Durandal | https://docs.px4.io/v1.15/en/flight_controller/durandal.html | feature list | STM32H7 at 480MHz, 2 MB flash, 1 MB RAM; exact part number not stated. |
| 6 | Holybro Pixhawk 4 | https://docs.px4.io/v1.15/en/flight_controller/pixhawk4.html | Quick Summary | STM32F765, Cortex-M7, 216MHz, 2MB memory, 512KB RAM; IO STM32F100, Cortex-M3, 24MHz, 8KB SRAM. |
| 7 | Mateksys H743 family | https://ardupilot.org/copter/docs/common-matekh743-wing.html | Specifications (Processor) | STM32H743VIT6 at 480MHz; flash and RAM not stated. |
| 8 | Mateksys F405-Wing | https://ardupilot.org/copter/docs/common-matekf405-wing.html | note before Specifications; Specifications | STM32F405RGT6 at 168MHz; the board does not include all ArduPilot features because of flash limits. |
| 9 | ArduPilot firmware limitations | https://ardupilot.org/plane/docs/common-limited-firmware.html | Firmware Limitations | ArduPilot firmware in some configurations exceeds 1 MB; no board names or image sizes on the page. |
| 10 | PX4 Loading Firmware (v1.12) | https://docs.px4.io/v1.12/en/config/firmware | FMUv2 Bootloader Update | early FMUv2 boards were restricted to 1MB of flash by a hardware issue; newer boards reach the full 2MB after a bootloader update. Context only; no FMUv2 board is in the profile table. |
| 11 | ST STM32H743/753 family | https://www.st.com/en/microcontrollers-microprocessors/stm32h743-753.html | description | Cortex-M7 up to 480 MHz; 1 to 2 Mbytes flash by variant; 1 Mbyte SRAM (192 KB TCM, user SRAM blocks, 4 KB backup). |
| 12 | ST STM32F765II | https://www.st.com/en/microcontrollers-microprocessors/stm32f765ii.html | description | Cortex-M7 up to 216 MHz; up to 2 Mbytes flash; 512 Kbytes SRAM including 128 Kbytes DTCM. |
| 13 | ST STM32F405/415 family | https://www.st.com/en/microcontrollers-microprocessors/stm32f405-415.html | description | Cortex-M4 at 168 MHz; 512 Kbytes to 1 Mbyte flash; 192 Kbytes SRAM. |
| 14 | ST STM32F405RG | https://www.st.com/en/microcontrollers-microprocessors/stm32f405rg.html | description | 1 Mbyte flash; up to 192+4 Kbytes SRAM including 64 Kbyte CCM data RAM; up to 168 MHz. |
| 15 | Raspberry Pi RP2040 | https://www.raspberrypi.com/products/rp2040/specifications/ | specifications | dual Cortex-M0+ up to 133 MHz; 264kB on chip SRAM; no on chip flash stated. |
| 16 | Raspberry Pi Pico | https://www.raspberrypi.com/products/raspberry-pi-pico/ | specification | RP2040; 264kB SRAM; 2MB on board QSPI flash. |
| 17 | Espressif ESP32-WROOM-32E | https://documentation.espressif.com/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.html | Section 1.1 Features | Xtensa dual core LX6 up to 240 MHz; 520 KB SRAM plus 16 KB RTC SRAM; 448 KB ROM; module flash 4, 8 or 16 MB. |

## 2. Refused or failed fetches (not worked around)

1. https://docs.px4.io/main/en/flight_controller/pixhawk6c.html, pixhawk4.html, durandal.html, cubepilot_cube_orange.html, matek_h743_slim.html (main branch), and https://docs.px4.io/v1.14/en/flight_controller/pixhawk6c.html: permission prompt not answered in time; not retried.
2. https://pip-assets.raspberrypi.com/categories/610-raspberry-pi-pico/documents/RP-008308-DS-1-pico-product-brief.pdf (redirect target of the Pico product brief): permission prompt not answered; the product page (row 16) was used instead.
3. https://firmware.ardupilot.org/Plane/stable/MatekF405-Wing/: refused by robots rules. This listing would have given a published firmware image size and allowed a free flash derivation.
4. https://docs.px4.io/v1.18/en/advanced_config/bootloader_update and https://docs.px4.io/main/zh/debug/binary_size_profiling.html: returned navigation only, no body text.

## 3. Gaps (why every free budget column is empty)

1. Free flash: no retrieved page gives the size of a PX4 or ArduPilot image for any of these boards, the bootloader size, or the flash reserved for parameters and logs. Without an image size, free flash = total flash minus image cannot be derived. The two flash limits recorded (Cube Orange fully accessible; Matek F405 limited by its 1 Mbyte) are limits, not free space.
2. Free RAM: no retrieved page gives the RAM used by the flight stack at run time. Free RAM cannot be derived.
3. Companion boards (Pico, ESP32): free budgets depend entirely on the application; nothing published applies.
4. Matek H743: the board page names the part (STM32H743VIT6) but the flash of that variant was not read on a retrieved page; the family minimum of 1 Mbyte is used as a lower bound.
5. Pixhawk 6C and Pixhawk 4: the board pages say "2MB memory" without naming flash. The ST family pages confirm flash of up to 2 Mbytes, so the value is read as flash; this reading is recorded as an interpretation.
6. Whether the boot verifier of each board can be updated in the field was not established from a retrieved page (the PX4 bootloader update page returned no body). The planner study keeps the synthetic values for `bootrom_verifier_updatable` and `updatable_bootloader_stage`.

Consequence used by `planner/profile_study.py`: with published totals only, the planner returns UNKNOWN for every device whose class depends on free memory (Rule 5), because every total is above every need. Free memory is therefore drawn from a stated assumption range, labelled assumption, and the range is varied.
