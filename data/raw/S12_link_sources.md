# S12 link sources (fourth round link simulator validation)

Author: Huda Mueen. Retrieval date for every entry: 2026-10-20. Values are paraphrased; short phrases only are quoted. Line numbers of this file are used as the `source` of the matching rows in `linksim/params.csv`.

## A. 6LoWPAN fragmentation (RFC 4944)

URL: https://www.rfc-editor.org/rfc/rfc4944.txt (Proposed Standard, retrieved 2026-10-20)
- A1. First fragment header: dispatch 11000, 11 bit datagram_size, 16 bit datagram_tag; 4 octets in total (Section 5.3, Figure 4).
- A2. Subsequent fragment header: dispatch 11100, datagram_size, datagram_tag and an 8 bit datagram_offset; 5 octets in total (Section 5.3, Figure 5).
- A3. datagram_offset counts in increments of 8 octets (Section 5.3).
- A4. Every link fragment of a datagram except the last must be a multiple of eight bytes long (Section 5.3).
- A5. Maximum physical layer packet 127 octets, maximum MAC frame 102 octets (25 octets of frame overhead), and only 81 octets left after the maximum AES-CCM-128 security overhead (Section 4).
- A6. Reassembly timeout at most 60 seconds (Section 5.3).
- A7. Uncompressed IPv6 dispatch is one octet; HC1 compresses a common IPv6 header to 2 octets plus the dispatch (Sections 5.1, 10.1, 12).

## B. IEEE 802.15.4 2.4 GHz timing and frame constants

The IEEE standard itself was not retrieved (paywalled). The values below come from operating system documentation and a peer reviewed analysis that state them.

B1. RIOT OS documentation, IEEE 802.15.4 header group. URL: https://api.riot-os.org/group__net__ieee802154__header.html (retrieved 2026-10-20; macro list)
- B1.1 Maximum frame length 127 octets (IEEE802154_FRAME_LEN_MAX).
- B1.2 ACK frame length 5 octets (IEEE802154_ACK_FRAME_LEN).
- B1.3 Maximum MAC header length 23 octets; frame control field 2 octets; frame check sequence 2 octets.
- B1.4 SIFS 12 symbols, LIFS 40 symbols, largest frame still followed by SIFS 18 octets.
- B1.5 aTurnaroundTime 12 symbols (citing IEEE Std 802.15.4-2020, Table 11-1).
- B1.6 CCA duration 8 symbols.
- B1.7 ACK timeout 54 symbols.
- B1.8 O-QPSK 2.4 GHz symbol time 16 microseconds (32 chips at 2 Mchip/s).
- B1.9 Default CSMA-CA minimum backoff exponent 3, maximum 5, maximum CSMA-CA retries 4, maximum frame retransmissions 4 (RIOT defaults).

B2. arXiv:1609.01101, "Performance analysis of a non-beacon enabled IEEE 802.15.4 network with retransmission and ACK mode". URL: https://arxiv.org/pdf/1609.01101 (retrieved 2026-10-20; Appendix A default attributes, and Section 3)
- B2.1 aUnitBackoffPeriod 20 symbols (Appendix A).
- B2.2 macMinBE 3, maximum BE 5, macMaxCSMABackoffs 4, frame retries 3 (Appendix A).
- B2.3 CCA 8 symbols, aTurnaroundTime 12 symbols, macAckWaitDuration 54 symbols, symbol 16 microseconds (Section 3 and Appendix A).
- B2.4 ACK frame 11 bytes on air, 22 symbols (Appendix A; consistent with a 5 octet ACK PSDU plus a 6 octet PHY header, see B3).

B3. tcpdump link type page for IEEE 802.15.4 non ASK PHY. URL: https://www.tcpdump.org/linktypes/LINKTYPE_IEEE802_15_4_NONASK_PHY.html (retrieved 2026-10-20)
- B3.1 Preamble 4 octets, SFD 1 octet, PHR 1 to 2 octets (1 octet taken for the 2.4 GHz O-QPSK PHY with a 127 octet PSDU, since 7 bits encode 127; the 1 octet choice is a reading, see unverified list).

B4. Rate: 250 kbps for the 2.4 GHz PHY is already cited (data/raw/S3_robotics.md:76, RFC 4919). B1.8 gives 16 microseconds per symbol; 4 bits per symbol is implied by 250 kbps and 16 microseconds, not stated separately.

## C. LoRa time on air

The Semtech application note AN1200.13 and the SX1276 data sheet were not retrieved (no search result offered them). The formula below is taken from a well documented open source page that attributes it to the Semtech SX1276 data sheet, so it is a secondary source.

C1. ifTNT/lora-air-time README. URL: https://github.com/ifTNT/lora-air-time (retrieved 2026-10-20)
- C1.1 Symbol time Ts = 2^SF / BW.
- C1.2 Packet time = Ts x ((n_preamble + 4.25) + n_payload).
- C1.3 n_payload = 8 + max(ceil((8 PL minus 4 SF + 28 + 16 CRC minus 20 IH) / (4 (SF minus 2 DE))) x (CR + 4), 0), with PL payload bytes, CRC 1 when on, IH 1 for implicit header, DE 1 when low data rate optimisation is on, CR 1 to 4 for 4/5 to 4/8.
- C1.4 Example: SF7, 125 kHz, CR 4/8, 11 byte payload, symbol time 1.024 ms, 32 payload symbols (preamble, header, CRC not stated).
- C1.5 Example: SF7, 125 kHz, CR 4/8, 11 byte payload, CRC on, explicit header: 40 payload symbols.
- C1.6 Example: SF12, 125 kHz, CR 4/6, 6 preamble symbols, 11 byte payload: total 794.624 ms, preamble 335.872 ms, payload 458.752 ms (CRC, header and DE not stated).

C2. The Things Network forum, "Spreadsheet for LoRa airtime calculation". URL: https://www.thethingsnetwork.org/forum/t/spreadsheet-for-lora-airtime-calculation/1190 (retrieved 2026-10-20)
- C2.1 LoRaWAN frame overhead 13 bytes: MHDR 1, DevAddr 4, FCtrl 1, FCnt 2, FPort 1, MIC 4 (posts 4 and 8).
- C2.2 LoRaWAN uses the explicit header; the payload CRC is part of the payload; low data rate optimisation on at SF11 and SF12 with 125 kHz (posts 11, 15, 16).
- C2.3 Example: a 13 byte header only packet at SF12 takes about 1.16 s (post 12; bandwidth 125 kHz, coding rate and preamble not stated).

C3. The Things Network forum, "Airtime calculator difference". URL: https://www.thethingsnetwork.org/forum/t/airtime-calculator-difference/67420 (retrieved 2026-10-20)
- C3.1 Confirms the 13 byte LoRaWAN overhead (MHDR 1, FHDR 7, FPort 1, MIC 4). Its numeric airtimes lack the full parameter set and are not used.

## D. EU868 duty cycle and data rates

D1. The Things Network, EU863-870 regional parameters (a secondary summary of the LoRa Alliance regional parameters). URL: https://www.thethingsnetwork.org/docs/lorawan/regional-parameters/eu868/ (retrieved 2026-10-20; Duty Cycle, Data Rates and Maximum Payload sections)
- D1.1 Recommended duty cycle limitation 1 percent in the European band.
- D1.2 ETSI EN 300 220 sub bands: K 863 to 865 MHz 0.1 percent; L 865 to 868 MHz 1 percent; M 868 to 868.6 MHz 1 percent; N 868.7 to 869.2 MHz 0.1 percent; P 869.4 to 869.65 MHz 10 percent; Q 869.7 to 870 MHz 1 percent.
- D1.3 DR0 SF12/125 kHz 250 bit/s; DR5 SF7/125 kHz 5470 bit/s; DR6 SF7/250 kHz 11000 bit/s.
- D1.4 Maximum MACPayload M 59 bytes at DR0 to DR2 and 230 at DR4 to DR7; application payload N = M minus 8 (51 and 222).
- D1.5 Daily airtime: 0.1 percent allows 86 s, 1 percent 864 s, 10 percent 8640 s.
- D1.6 RX1 and RX2 delays are not stated on this page.

D2. The Things Network, duty cycle page. URL: https://www.thethingsnetwork.org/docs/lorawan/duty-cycle/index.html (retrieved 2026-10-20)
- D2.1 Duty cycle is the fraction of time a resource is busy; ETSI EN 300 220-2 section 4.3.3 sets the sub band limits above; a sub band limit may be divided over its channels.
- D2.2 The page gives no off time example. For a 1 percent limit, an airtime T must be followed by 99 T of silence; this is derived from the definition, not stated.

## E. EDHOC message sizes

E1. IETF draft-ietf-lake-edhoc-17 (October 2022; later published as RFC 9528; draft text, standard was in flux at that time). URL: https://datatracker.ietf.org/doc/html/draft-ietf-lake-edhoc-17 (retrieved 2026-10-20; Section 1.2, Figure 1)
- E1.1 Credentials by reference (kid), signature keys: message_1 37 bytes, message_2 102 bytes, message_3 77 bytes, total 216.
- E1.2 Credentials by reference, static DH keys: 37, 45, 19 bytes, total 101.
- E1.3 The figure relies on assumptions in an external comparison draft (cipher suite and signature size not stated in the retrieved text).

## F. Not retrieved or not used

- F1. IEEE 802.15.4 standard text: paywalled, not retrieved; constants taken from B1 to B3.
- F2. Semtech AN1200.13 and SX1276 data sheet: not offered by search; formula from C1 (secondary).
- F3. LoRaWAN RX1 delay: not retrieved; the existing ASSUMPTION turnaround_lorawan_s stays.
- F4. DTLS 1.3 record overhead, OSCORE overhead, DDS Security handshake sizes, certificate sizes: not retrieved; these are ASSUMPTIONS in linksim/params.csv and are swept.
- F5. NB-IoT and Wi-Fi parameters: not retrieved; no Wi-Fi or cellular profile is simulated.
- F6. Blocked fetches (access to the site not granted in time): https://raw.githubusercontent.com/RIOT-OS/RIOT/master/sys/include/net/ieee802154.h, https://raw.githubusercontent.com/torvalds/linux/master/include/linux/ieee802154.h, and a first attempt at the D1 page (the D1 page was later retrieved through a search result).
- F7. Semtech forum threads https://forum.lora-developers.semtech.com/t/sx126x-time-on-air-calculation/127 and https://forum.lora-developers.semtech.com/t/parameters-explanation-for-time-on-air/1357 were read; Semtech staff declined to give the formula there, so they are not used.
