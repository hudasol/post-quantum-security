# SROS2 / DDS-Security upstream draft

Status: DRAFT NOT FILED. Nothing has been posted, commented on or reacted to.
Author of the eventual text: Huda Mueen.

## Existing upstream items found

NONE VERIFIED. The duplicate check for this draft is INCOMPLETE. The GitHub repository search's search returned zero results for "post-quantum cryptography" in ros2/sros2 and eProsima/Fast-DDS, but the same search returned zero in mavlink/mavlink where issues #2525 and #2527 demonstrably exist, so a zero result from that tool is not evidence of absence. The repository search then stopped and the public API was blocked, so I could not read issue lists, pull requests or discussions for ros2/sros2, ros2/ros2, ros2/design, ros2/rmw, eProsima/Fast-DDS, ros2/rmw_zenoh, or ROS Discourse. Do not file until the checklist below is done. If an existing thread covers these questions, convert this draft into a short comment that links it.

What this repository already recorded (data/raw/S3_robotics.md section 3.4, retrieved 2026-10-11) as research forks, not upstream threads: PQSec-DDS (Blanco Romero et al., JNIC 2024, https://idus.us.es/bitstream/handle/11441/160619/JNIC24_414.pdf), a master's thesis with a Dilithium3 SROS2 fork (https://dspace.umh.es/bitstream/11000/37017/1/Blanco_Romero_Francisco_Javier_TFM.pdf), and the AXON preprint (https://arxiv.org/pdf/2609.10024). If any of these authors opened upstream issues, they would be the first thing to find.

## Venue and process (retrieved now)

- ros2/sros2: CONTRIBUTING.md covers Apache 2 licensing and DCO sign off only; no issue template, no PR template (404 at .github paths on the rolling branch); README states it was tested against eProsima Fast DDS, Eclipse Cyclone DDS and RTI Connext (https://raw.githubusercontent.com/ros2/sros2/rolling/README.md).
- ros2 organisation issue routing (https://raw.githubusercontent.com/ros2/.github/master/.github/ISSUE_TEMPLATE/config.yml): usage questions go to Robotics Stack Exchange; "discuss a ROS feature" goes to ROS Discourse; real time developer conversation goes to Zulip "ROS General". Blank issues are enabled.
- ros2/.github/profile README names Zulip as best for developer conversations (https://raw.githubusercontent.com/ros2/.github/master/profile/README.md).
- eProsima/Fast-DDS: blank issues disabled; issue config points to CONTRIBUTING.md, which has an "Issues and Support" section that I only saw in the table of contents and have not read (https://raw.githubusercontent.com/eProsima/Fast-DDS/master/CONTRIBUTING.md).
- ROS design norms (REP process, design.ros2.org posting rules) were NOT retrieved. Unverified.

Recommended venue: ROS Discourse, as a question post (the organisation routing sends "discuss a feature" there), with a link to it from a short sros2 issue only if sros2 maintainers ask. The text below is written to work as a Discourse post; it also fits a GitHub issue if the checks show that is preferred.

## Title

Is post quantum authentication and key agreement for DDS-Security and SROS2 planned or being discussed?

## Body

Hello,

I am Huda Mueen. I am writing a sourced review of post quantum cryptography on drone and robot computers, and I would like to ask a few questions so that I describe the ROS 2 position accurately. I am not proposing a change.

What I found when reading the primary sources on 2026-10-11:

- DDS Security 1.2 (OMG document formal/25-03-06, cover marked "Release Date: Tbd 2025") lists RSASSA-PSS and PKCS#1 v1.5 (2048 bit), ECDSA P-256 and P-384, DHE with MODP-2048 and ECDHE with P-256 and P-384, with AES-GCM and GMAC. A text search of the document found no post quantum algorithm. Source: https://www.omg.org/spec/DDS-SECURITY/1.2/PDF
- The ROS 2 design article "ROS 2 DDS-Security integration" describes use of the authentication, access control and cryptographic plugin interfaces with X.509 certificates and signed governance and permissions files. Source: https://design.ros2.org/articles/ros2_dds_security.html
- I did not find post quantum support in sros2, Fast DDS, Cyclone DDS or Connext release notes, but I did not check vendor release notes exhaustively.
- Research work exists outside the upstream projects (PQSec-DDS for Cyclone DDS, and a thesis fork of SROS2), and I found no published benchmark of a post quantum DDS-Security handshake on a robot class or microcontroller class processor.

For scale, the FIPS 204 ML-DSA-44 signature is 2420 bytes (https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf, Table 2), compared with a P-256 ECDSA signature of at most about 72 bytes in DER form; I mention this only because certificate and permissions files would grow.

My questions:

1. Is there an existing issue, REP, design discussion or working group note on post quantum algorithms for SROS2 or DDS-Security that I should read instead of asking here? If so, I will link it in my review and withdraw this post.
2. Where do you expect algorithm agility to live: in the OMG DDS-Security specification (so the DDS vendors implement it), in the DDS vendor plugins, or in the ROS layer (for example in sros2 key and certificate generation)?
3. Is the ROS 2 security working group, or another group, the right place to follow this topic, and is there a public meeting record?
4. For the Zenoh based RMW, is post quantum key agreement expected to come from the underlying TLS or QUIC library rather than from ROS 2 itself?

Thank you for your time. I will cite any answer with a link and will not describe it as an official position unless you say so.

Huda Mueen

## Links

- https://www.omg.org/spec/DDS-SECURITY/1.2/PDF
- https://design.ros2.org/articles/ros2_dds_security.html
- https://github.com/ros2/sros2
- https://raw.githubusercontent.com/ros2/.github/master/.github/ISSUE_TEMPLATE/config.yml
- https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf
- https://idus.us.es/bitstream/handle/11441/160619/JNIC24_414.pdf
- https://dspace.umh.es/bitstream/11000/37017/1/Blanco_Romero_Francisco_Javier_TFM.pdf

## Items to verify before filing

- The "at most about 72 bytes" ECDSA DER figure is general knowledge, not from a source retrieved in this repository. Either cite a source for it or delete that clause.
- Statement about the Zenoh RMW (question 4) rests on data/raw/S3_robotics.md section 3.2, which saw only that the tutorial covers rmw_zenoh_cpp. Re-read the tutorial before asking.
- DDS-Security 1.2 may have been finalised since 2026-10-11; recheck the cover page.

## Pre filing checklist

- [ ] Complete the duplicate search with the repository search reconnected (or by hand on GitHub): issues, pull requests and discussions in ros2/sros2, ros2/ros2, ros2/design, ros2/rmw, ros2/rmw_zenoh, ros2/rmw_fastrtps, ros2/rmw_cyclonedds, eProsima/Fast-DDS, eclipse-cyclonedds/cyclonedds; ROS Discourse, Zulip and Robotics Stack Exchange searches; terms: post-quantum, PQC, quantum, ML-DSA, Dilithium, ML-KEM, Kyber, LMS, XMSS, SLH-DSA, hybrid signature.
- [ ] If any match is found, replace this draft with a short comment that links it.
- [ ] Read the Fast-DDS CONTRIBUTING "Issues and Support" section and ROS Discourse posting guidelines; reformat accordingly.
- [ ] Confirm no change to DDS-Security status (final or not).
- [ ] Check wording: no em dashes, no hyphens between words except in names, no emojis, no affiliation, no claim of authority, 4 questions or fewer, no attack details.
- [ ] Huda to read and approve; nothing is posted until the author approves it.
