# S12 energy and CPU headroom sources

Author: Huda Mueen. Retrieval date for every entry: 2026-10-20. Retrieved with the web fetch and web search tools. Values are paraphrased; short phrases only are quoted. Every value below is copied into `energy/parts.csv`, `energy/platforms.csv` or `energy/retrieved_benchmarks.csv`, and those files are the only place the scripts read them from.

## 1. Microcontroller run mode current

Vendor product pages give one headline figure per part. None of these pages states the temperature, the code location (flash or SRAM), the cache or accelerator state, or whether the figure is typical or maximum. These conditions are recorded as `not stated` in `energy/parts.csv`. The full datasheet tables (which carry the conditions) were not retrieved; see section 4.

| Part | Core | Value as stated | Conditions as stated | URL | Location |
|---|---|---|---|---|---|
| STM32L4R5 | Cortex-M4 | 110 uA/MHz Run mode (LDO mode); 43 uA/MHz Run mode at 3.3 V SMPS mode | max 120 MHz; VDD 1.71 to 3.6 V with internal LDO | https://www.st.com/en/microcontrollers-microprocessors/stm32l4r5zg.html | product page, feature list |
| STM32L476 | Cortex-M4 | 100 uA/MHz run mode (LDO mode); 39 uA/MHz run mode at 3.3 V SMPS mode | max 80 MHz; VDD 1.71 to 3.6 V with internal LDO | https://www.st.com/en/microcontrollers-microprocessors/stm32l476rg.html | product page, feature list |
| STM32L552 | Cortex-M33 | 106 uA/MHz Run mode (LDO mode); 62 uA/MHz Run mode at 3 V (SMPS step down mode) | max 110 MHz; 1.71 to 3.6 V; one HASH hardware accelerator listed | https://www.st.com/en/microcontrollers/stm32l552ze.html | product page, feature list |
| STM32U5A5 | Cortex-M33 | 18.5 uA/MHz Run mode at 3.3 V (regulator not stated on the page) | max 160 MHz; 1.71 to 3.6 V; HASH accelerator, PKA and AES listed without throughput | https://www.st.com/en/microcontrollers-microprocessors/stm32u5a5zj.html | product page, feature list |
| ESP32-C3 | RISC-V (32 bit) | 23 mA at 160 MHz, CPU running, all peripheral clocks disabled (28 mA with peripheral clocks enabled); 17 mA at 80 MHz running | typical; Modem-sleep mode (RF off); supply voltage not stated in this table (section 5.6.1 uses 3.3 V, 25 C for the RF tables); flash access can add about 10 mA | https://documentation.espressif.com/esp32-c3_datasheet_en.html | ESP32-C3 Series Datasheet v2.4, section 5.6.2, Table 5-8 "Current Consumption in Modem-sleep Mode" (page 57 per the fetch) |
| STM32F405 | Cortex-M4 | not found | product page states 168 MHz and 1.8 to 3.6 V only | https://www.st.com/en/microcontrollers-microprocessors/stm32f405rg.html | product page |
| STM32H743 | Cortex-M7 | not found (only a Standby figure on the page) | 480 MHz; 1.62 to 3.6 V | https://www.st.com/en/microcontrollers-microprocessors/stm32h743zi.html | product page |
| STM32H743/H753 | Cortex-M7 | no CPU run current; Table 18 gives whole application averages (18.7 mA at HCLK 64 MHz, 3.3 V, mode 1) which are not CPU run figures and are not used | | https://www.st.com/resource/en/application_note/dm00368706-stm32h7x3-smart-power-management-expansion-package-for-stm32cube-stmicroelectronics.pdf | AN, Table 18, page 40 |
| STM32H563 | Cortex-M33 | not found | 250 MHz; HASH accelerator and ECDSA signature verification listed without throughput | https://www.st.com/en/microcontrollers/stm32h563zi.html | product page |
| nRF52840 | Cortex-M4 | not found (product page gives the 64 MHz clock only) | | https://www.nordicsemi.com/Products/nRF52840 | product page |
| GD32VF103 | RISC-V (Bumblebee) | not found (product page lists datasheet Rev 2.3 without a link) | 108 MHz; 2.6 to 3.6 V | https://www.gigadevice.com/product/mcu/main-stream-mcus/gd32vf103-series | product page |

## 2. Software and hardware SHA-256 throughput and classical public key timings

CycloneCRYPTO 2.5.0 benchmark pages (Oryx Embedded), all compiled with ARMCC at optimisation level 3. The unit "MB/s" is not defined on the pages; the scripts treat it as 10^6 bytes per second and record this as an assumption. Statistic and number of runs are not stated.

| Board, core, clock | SHA-256 software | SHA-256 hardware | Ed25519 verify | ECDSA P-256 verify | X25519 shared secret | URL |
|---|---|---|---|---|---|---|
| NUCLEO-F439ZI (STM32F439ZI), Cortex-M4, 180 MHz | 2.36 MB/s | 75.757 MB/s | 14.5 ms | 59.2 ms | 8.9 ms | https://oryx-embedded.com/benchmark/st/crypto-stm32f4.html |
| ATSAM4C32-EK (SAM4C), Cortex-M4, 120 MHz | 1.095 MB/s | 62.893 MB/s | 26.8 ms | 114.9 ms (software) | 16.3 ms | https://www.oryx-embedded.com/benchmark/microchip/crypto-sam4c.html |
| NuMaker-IoT-M487 (M487), Cortex-M4, 192 MHz | 2.557 MB/s | 37.313 MB/s | 13.2 ms | 56.8 ms (software) | 8.3 ms | https://www.oryx-embedded.com/benchmark/nuvoton/crypto-m487.html |

Locations: tables "Hash Algorithms", "EC Signature Algorithms" and "EC Key Exchange Algorithms" on each page. HMAC-SHA256 is not listed on any of the three pages.

## 3. Reference platforms

| Platform | Statement | URL | Location |
|---|---|---|---|
| Bitcraze Crazyflie 2.1 (small multirotor kit) | main MCU STM32F405 (Cortex-M4, 168 MHz, 192 kB SRAM, 1 MB flash); radio MCU nRF51822; 250 mAh LiPo battery; flight time with stock battery 7 minutes; takeoff weight 29 g; battery voltage not stated | https://www.bitcraze.io/documentation/hardware/crazyflie_2_1/crazyflie_2_1-datasheet.pdf | Datasheet Rev 3 (2021-11-15): sections 3, 5, 8 and 10, pages 1 to 3 |
| ROBOTIS TurtleBot3 Burger (small ground robot) | battery lithium polymer 11.1 V 1800 mAh, 19.98 Wh, 5C; expected operating time 2 h 30 min; MCU 32 bit Cortex-M7 with FPU at 216 MHz; SBC Raspberry Pi 4 | https://emanual.robotis.com/docs/en/platform/turtlebot3/features/ | Specifications, Hardware Specifications table |

The Crazyflie cell voltage is not stated in the retrieved datasheet. The scripts use a one cell LiPo voltage range as a labelled assumption (`unverified`).

## 4. Refused, blocked or failed retrievals

| URL | Result |
|---|---|
| https://www.st.com/resource/en/datasheet/stm32l4r5vi.pdf | refused (permission prompt not answered); not retried, no mirror used |
| https://www.st.com/resource/en/datasheet/stm32f405rg.pdf | refused (permission prompt not answered); not retried, no mirror used |
| https://docs.nordicsemi.com/bundle/ps_nrf52840/page/_tmp/nrf52840/autodita/CURRENT/parameters.i_cpu.html | refused (permission prompt not answered) |
| https://infocenter.nordicsemi.com/pdf/nRF52840_PS_v1.8.pdf | redirected to the documentation home page; content not obtained |
| https://documentation.espressif.com/api/resource/doc/file/aYwvqd1B/FILE/esp32-c3_datasheet_en.pdf | server error 500; the HTML datasheet on the same vendor site was used instead |
| https://docs.px4.io/main/zh/debug/binary_size_profiling | page body not returned |
| https://docs.zephyrproject.org/latest/samples/drivers/hash_bench/README.html | no measured values on the page |

RP2040 and the GD32VF103 datasheet: only third party copies appeared in search results; under the no mirror rule they were not fetched. Their rows in `energy/parts.csv` are empty.
