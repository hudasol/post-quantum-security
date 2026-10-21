# Sources of the network simulator check (fifth round)

Author: Huda Mueen. Retrieval date for every entry: 2026-10-21 (UTC 2026-10-20 evening). Values are paraphrased; short phrases only are quoted. Identifiers N1 to N7 are used by `netsim/cells.py`, `linksim/checks.py` and `docs/NETSIM_STUDY.md`.

## N1. IEEE 802.15.4 MAC PIB ranges

Microchip, MPLAB Harmony Wireless 15.4 MAC API Reference Manual, section 3.1 "MAC PIB List", Table 3-1. URL: https://onlinedocs.microchip.com/oxy/GUID-D769F037-FBC7-4D1C-9892-ADA91E643160-en-US-2/GUID-87A1FB09-3E4E-468D-8622-7A660E9B12B6.html

- N1.1 macMinBE default 3, range 0 to macMaxBE.
- N1.2 macMaxBE default 5, range 3 to 8.
- N1.3 macMaxCSMABackoffs default 4, range 0 to 5.
- N1.4 macMaxFrameRetries default 3, range 0 to 7.

This is a vendor manual that restates the PIB of the standard; the IEEE standard itself was not retrieved (paywalled, see data/raw/S12_link_sources.md F1).

## N2. ns-3 lr-wpan module at tag ns-3.48

Source code fetched by `netsim/fetch_build.sh` (https://github.com/nsnam/ns-3-dev-git, tag ns-3.48).

- N2.1 `src/lr-wpan/model/lr-wpan-csmaca.h`: macMinBE "0 - macMaxBE, default 3"; macMaxBE "3 - 8, default 5"; macMaxCSMABackoffs "0 - 5, default 4"; the setters cite IEEE 802.15.4-2006 section 7.4.2, Table 86, and assert these ranges.
- N2.2 `src/lr-wpan/model/lr-wpan-mac.cc`: macMaxFrameRetries default 3.
- N2.3 `src/lr-wpan/model/lr-wpan-net-device.cc`: attribute UseAcks, default true.
- N2.4 `src/lr-wpan/model/lr-wpan-phy.cc`: receiver sensitivity default -106.58 dBm; transmit power PIB default 0; clear channel assessment reports busy at 10 dB above the sensitivity.

## N3. signetlabdei lorawan module at tag v0.3.7

Source code fetched by `netsim/fetch_build.sh` (https://github.com/signetlabdei/lorawan, commit a13219eebab664729eeed2694fa1cedf89e9c8d8; its NS3-VERSION file reads "release ns-3.48").

- N3.1 `model/lora-phy.cc` LoraPhy::GetTimeOnAir: preamble (n_preamble + 4.25) symbols; payload symbols 8 + max(ceil((8 PL - 4 SF + 28 + 16 CRC - 20 H) / (4 (SF - 2 DE))) (CR + 4), 0), based on the Semtech SX1272 LoRa modem designer's guide as the code comment states.
- N3.2 `model/class-a-end-device-lorawan-mac.cc`: transmissions use CRC on, low data rate optimisation for SF11 and SF12 at 125 kHz, the device preamble length and coding rate (default CR 4/5, `model/end-device-lorawan-mac.cc`).
- N3.3 `model/lora-frame-header.cc`: frame header 8 B (DevAddr 4, FCtrl 1, FCnt 2, FPort 1) plus options; `model/lorawan-mac-header.cc`: MAC header 1 B; `model/end-device-lorawan-mac.cc` line "TODO: Add MIC": no 4 B message integrity code is added. The module's frame overhead is therefore 9 B, against 13 B in data/raw/S12_link_sources.md C2.1.
- N3.4 `model/end-device-lorawan-mac.cc` Send: a packet that the duty cycle or the receive windows do not allow is postponed by the MAC; a new Send cancels a queued one.

## N4. Selective repeat expected transmissions

A. S. H. Mahmoud, COE 540 Computer Networks lecture slides (term 081), King Fahd University of Petroleum and Minerals. URL: https://faculty.kfupm.edu.sa/coe/ashraf/RichFilesTeaching/COE081_540/Lecture_COE_540_081_3.pdf

- N4.1 Slide 27, "Selective Reject ARQ, Efficiency With Errors": a data frame is in error with probability P; Nr, the expected number of transmitted frames to successfully transmit one frame, equals the sum over i of i P^(i-1) (1 - P) = 1 / (1 - P); only the frame in error is retransmitted.
- N4.2 Slide 29: errors in acknowledgements are ignored in the utilisation curves.

N5. University of Calgary CPSC 441 lecture 3.2 slide "Performance of Selective Repeat with Errors". URL: https://cspages.ucalgary.ca/~unger/441/lectures/3.2/tsld019.htm

- N5.1 States Nr = sum f(i) P^(i-1) (1 - P) = 1 / (1 - P) and U = 1 - P for a large enough window. Secondary to N4; definitions are on a previous slide that was not retrieved (see refused list).

## N6. ePrint 2021/781 (supplied PDF)

`/mnt/user-data/uploads/sources/` file "2021-781 Quantum-Resistant Security for Software Updates on Low-power Networked Embedded Devices.pdf".

- N6.1 Pages 15 to 16: "it takes 30-60s to transfer 50kB on a low-power IEEE802.15.4 radio link, depending on link quality and network load (assuming non-extreme cases)". No PHY, MAC, hop count, distance, load or protocol setting is stated there.
- N6.2 Section 3.1: the device fetches the update from a repository, for example a CoAP resource directory.
- N6.3 Section 5.1: the hardware testbed uses the Nordic nRF52840 Development Kit (a 2.4 GHz board); no network experiment is described.

## N7. Version pins

- N7.1 ns-3 release tags listed by `git ls-remote --tags https://github.com/nsnam/ns-3-dev-git` include ns-3.48 and ns-3.49; ns-3.48 was chosen because the lorawan module's latest release (v0.3.7) and its develop branch both state "release ns-3.48".

## Refused or not retrieved

- https://cspages.ucalgary.ca/~unger/441/lectures/3.2/tsld018.htm (the slide before N5): access to the page was not granted in time; not used.
- https://web.mit.edu/course/16/16.682/www/lec15.pdf was read; it gives the efficiency 1 - P of ideal selective repeat but no transmission count, so it is not cited for the check.
- https://kilyos.ee.bilkent.edu.tr/~ee538/lecture2.pdf was read; it has only a heading for selective repeat; not used.
- arXiv:1609.01101 was read again for parameter ranges; it gives defaults only (already in data/raw/S12_link_sources.md B2), not ranges.
