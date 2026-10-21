# S12 traffic sources for the mission study

Author: Huda Mueen. Retrieval date for every item: 2026-10-20. Retrieved with the web fetch and web searchs unless stated. Values are paraphrased; short phrases only are quoted.

## 1. Retrieved and used

| id | URL | location in source | fact used |
|---|---|---|---|
| T1 | https://ardupilot.org/dev/docs/mavlink-requesting-data.html | section on SRx_ parameters | SRx_ parameters set the rate of message groups per telemetry port, in Hz; "x" matches the port (Telem1 uses SR1_). Groups (Copter 4.0): SRx_EXTRA1 carries ATTITUDE (with SIMSTATE, AHRS2, AHRS3, PID_TUNING); SRx_POSITION carries GLOBAL_POSITION_INT and LOCAL_POSITION_NED; SRx_EXTRA2 carries VFR_HUD; SRx_EXT_STAT carries SYS_STATUS, POWER_STATUS, MEMINFO, MISSION_CURRENT, GPS_RAW_INT, NAV_CONTROLLER_OUTPUT, POSITION_TARGET_GLOBAL_INT and others; SRx_EXTRA3 carries BATTERY_STATUS, SYSTEM_TIME, VIBRATION, EKF_STATUS_REPORT and others; SRx_RC_CHAN carries SERVO_OUTPUT_RAW and RC_CHANNELS; SRx_RAW_SENS carries RAW_IMU, SCALED_PRESSURE and others. No default values and no maximum rate are stated on the page. |
| T2 | same page | section on SET_MESSAGE_INTERVAL | Per message rates are set with COMMAND_LONG carrying MAV_CMD_SET_MESSAGE_INTERVAL (511), param2 the interval in microseconds (100000 gives 10 Hz); supported from ArduPilot 4.0. |
| T3 | https://docs.px4.io/v1.13/en/peripherals/mavlink_peripherals.html | sections "MAV_X_RATE" and default instance settings | MAV_X_RATE is the combined maximum data rate of all streams of an instance in bytes per second; PX4 lowers individual message rates when the streams exceed it. TELEM1 default: MAV_0_MODE Normal, MAV_0_RATE 1200 B/s, SER_TEL1_BAUD 57600. The page does not give per message default rates. This is the v1.13 page (an older documentation version; newer versions may differ). |
| T4 | https://mavlink.io/ko/guide/message_rates.html | page body and implementation section | MAV_CMD_SET_MESSAGE_INTERVAL sets rates per link; flight stacks set default rates with parameters (PX4 MAV_*_RATE); supported on PX4 v1.11+ and ArduPilot v4.0+. No default rates are stated. (Korean language mirror path on the official mavlink.io site, listed by the search tool; the text retrieved was in English.) |
| T5 | https://ardupilot.org/dev/docs/mavlink-basics.html | packet structure and HEARTBEAT sections | Each system sends HEARTBEAT "at 1hz" once a connection is open; MAVLink 2 messages have a maximum of 280 bytes. |
| T6 | https://ardupilot.org/copter/docs/ArduCopter_MAVLink_Messages.html | requestable and incoming message tables | Message ids HEARTBEAT 0, GPS_RAW_INT 24, ATTITUDE 30, GLOBAL_POSITION_INT 33, COMMAND_LONG 76, BATTERY_STATUS 147. No field types or lengths stated. |
| T7 | https://community.rti.com/static/documentation/wireshark/2023-09/doc/understanding_rtps.html | security submessages section | RTPS security submessages SEC_PREFIX, SEC_BODY, SEC_POSTFIX, SRTPS_PREFIX, SRTPS_POSTFIX and transformation kinds AES128_GMAC, AES128_GCM, AES256_GMAC, AES256_GCM exist; the text gives no byte sizes (field diagrams are images that the retrieval could not read). |

Existing repository sources reused (not retrieved again): link parameters in `linksim/params.csv` (cited to `data/raw/S3_robotics.md`), the SiK `MAX_PACKET_LENGTH` of 252 B (`data/raw/S3_robotics.md`, section 2.2), board clocks in `data/raw/S5_benchmark_plan_facts.md` lines 75 to 77.

## 2. Host measured: MAVLink payload lengths

The common message definitions page on mavlink.io could not be retrieved (see Section 4). Payload lengths were therefore measured on the host from the generated message classes of pymavlink 2.4.50 (installed from PyPI into a virtual environment outside the repository; LGPL 3.0 per its package metadata), by reading the packed size of each message structure including extension fields. Script: `mission/measure_payloads.py`; output: `mission/payload_lengths.csv` (label host measured). These are maximum lengths; MAVLink 2 removes trailing zero bytes from the payload on the wire, so real frames can be shorter.

## 3. Not found or unverified

- Default SRx_ stream rates for ArduPilot: not stated on the retrieved page; unverified. The mission study uses explicit assumptions (`mission/traffic.csv`, label assumption).
- PX4 per message default rates in Normal mode: not stated on the retrieved page; unverified.
- ROS 2 DDS Security per message overhead in bytes: not stated in any retrieved text; unverified. The ground robot is therefore modelled with MAVLink framing (as used by rover firmware), not with DDS framing.

## 4. Refused or blocked retrievals

| URL | result |
|---|---|
| https://mavlink.io/en/messages/common.html | fetch not completed; not retried |
| https://ardupilot.org/copter/docs/parameters.html | fetch not completed; not retried |
| https://fast-dds.docs.eprosima.com/en/latest/fastdds/security/crypto_plugin/crypto_plugin.html | fetch not completed (redirect target of the eProsima readthedocs URL); not retried |

## 5. Search queries run (web search)

- "MAVLink common message definitions HEARTBEAT ATTITUDE GLOBAL_POSITION_INT COMMAND_LONG field types"
- "ArduPilot SR0_POSITION SR0_EXTRA1 telemetry stream rate parameters Hz default"
- "PX4 MAVLink streaming rates mavlink stream command message rate default telemetry"
- "DDS Security RTPS SEC_PREFIX SEC_POSTFIX submessage overhead bytes AES-GCM GMAC per message"

Mirrors of `common.xml` that appeared in the results were not used, because the official page had been refused.
