# Board predictions, registered before any board session

Author: Huda Mueen. Written 2026-10-20 from `cyclemodel/results/board_predictions.csv` (label: modelled) before any board was borrowed. The SHA-256 of this file as committed is in `docs/PREDICTIONS_V4_BOARD.sha256`; it is never edited after the hash is taken. The board session (`docs/BOARD_RUN_PROTOCOL.md`, `bench/board_kit/`) scores each prediction: a hit if the board measured median lies inside the registered interval, a miss otherwise. Misses stay.

Conditions assumed by the model: Cortex-M4 at zero flash wait states, no cache, no bus contention, compiler arm-none-eabi-gcc 13.2.1. For the repository harness (mlkem-native and mldsa-native) the instruction mix lies outside the training rows, so the registered interval is the envelope of the full and reduced fits. For the pqm4 B0 rows the registered interval is the 95 percent prediction interval of the full fit.

| ID | target | parameter set | implementation | operation | point prediction (cycles) | registered interval (cycles) |
|---|---|---|---|---|---|---|
| BP1 | harness (bench/mcu) | ML-DSA-44 | mldsa-native v2.0.0 -O2 | keygen | 2,952,835 | 2,169,561 to 3,472,512 |
| BP2 | harness (bench/mcu) | ML-DSA-44 | mldsa-native v2.0.0 -O2 | sign | 6,627,144 | 4,576,154 to 7,793,471 |
| BP3 | harness (bench/mcu) | ML-DSA-44 | mldsa-native v2.0.0 -O2 | verify | 3,072,038 | 2,215,990 to 3,612,693 |
| BP4 | harness (bench/mcu) | ML-DSA-65 | mldsa-native v2.0.0 -O2 | keygen | 5,110,942 | 3,752,787 to 6,010,429 |
| BP5 | harness (bench/mcu) | ML-DSA-65 | mldsa-native v2.0.0 -O2 | sign | 12,488,262 | 8,820,068 to 14,686,101 |
| BP6 | harness (bench/mcu) | ML-DSA-65 | mldsa-native v2.0.0 -O2 | verify | 5,085,279 | 3,711,897 to 5,980,250 |
| BP7 | harness (bench/mcu) | ML-DSA-87 | mldsa-native v2.0.0 -O2 | keygen | 8,648,442 | 6,376,749 to 10,170,502 |
| BP8 | harness (bench/mcu) | ML-DSA-87 | mldsa-native v2.0.0 -O2 | sign | 16,755,536 | 11,925,628 to 19,704,383 |
| BP9 | harness (bench/mcu) | ML-DSA-87 | mldsa-native v2.0.0 -O2 | verify | 8,620,866 | 6,311,032 to 10,138,073 |
| BP10 | harness (bench/mcu) | ML-KEM-1024 | mlkem-native v2.0.0 -O2 | decaps | 2,568,234 | 1,986,449 to 3,020,224 |
| BP11 | harness (bench/mcu) | ML-KEM-1024 | mlkem-native v2.0.0 -O2 | encaps | 2,145,940 | 1,655,488 to 2,523,610 |
| BP12 | harness (bench/mcu) | ML-KEM-1024 | mlkem-native v2.0.0 -O2 | keygen | 1,971,951 | 1,507,989 to 2,319,000 |
| BP13 | harness (bench/mcu) | ML-KEM-512 | mlkem-native v2.0.0 -O2 | decaps | 1,107,387 | 867,764 to 1,302,279 |
| BP14 | harness (bench/mcu) | ML-KEM-512 | mlkem-native v2.0.0 -O2 | encaps | 870,110 | 680,355 to 1,023,243 |
| BP15 | harness (bench/mcu) | ML-KEM-512 | mlkem-native v2.0.0 -O2 | keygen | 787,125 | 609,153 to 925,653 |
| BP16 | harness (bench/mcu) | ML-KEM-768 | mlkem-native v2.0.0 -O2 | decaps | 1,746,494 | 1,357,352 to 2,053,864 |
| BP17 | harness (bench/mcu) | ML-KEM-768 | mlkem-native v2.0.0 -O2 | encaps | 1,417,068 | 1,099,244 to 1,666,461 |
| BP18 | harness (bench/mcu) | ML-KEM-768 | mlkem-native v2.0.0 -O2 | keygen | 1,267,580 | 973,426 to 1,490,664 |
| BP19 | pqm4 B0 | ML-DSA-44 | clean | keygen | 1,844,300 | 1,680,155 to 2,168,883 |
| BP20 | pqm4 B0 | ML-DSA-44 | clean | sign | 6,978,918 | 6,357,782 to 8,207,154 |
| BP21 | pqm4 B0 | ML-DSA-44 | clean | verify | 2,027,299 | 1,846,866 to 2,384,088 |
| BP22 | pqm4 B0 | ML-DSA-44 | m4f | keygen | 1,440,368 | 1,312,173 to 1,693,862 |
| BP23 | pqm4 B0 | ML-DSA-44 | m4f | sign | 3,801,958 | 3,463,578 to 4,471,074 |
| BP24 | pqm4 B0 | ML-DSA-44 | m4f | verify | 1,469,782 | 1,338,969 to 1,728,452 |
| BP25 | pqm4 B0 | ML-KEM-768 | clean | decaps | 1,391,990 | 1,268,100 to 1,636,970 |
| BP26 | pqm4 B0 | ML-KEM-768 | clean | encaps | 1,145,848 | 1,043,866 to 1,347,509 |
| BP27 | pqm4 B0 | ML-KEM-768 | clean | keygen | 970,779 | 884,378 to 1,141,628 |
| BP28 | pqm4 B0 | ML-KEM-768 | m4fspeed | decaps | 699,432 | 637,181 to 822,527 |
| BP29 | pqm4 B0 | ML-KEM-768 | m4fspeed | encaps | 652,963 | 594,848 to 767,880 |
| BP30 | pqm4 B0 | ML-KEM-768 | m4fspeed | keygen | 648,055 | 590,377 to 762,107 |

Refuted for an operation if the board measured median lies outside its registered interval. The model is refuted overall if more than a third of the operations miss.
