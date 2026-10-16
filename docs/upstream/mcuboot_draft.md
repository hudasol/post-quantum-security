# MCUboot upstream draft

Status: DRAFT NOT FILED. Nothing has been posted, commented on or reacted to.
Author of the eventual text: Huda Mueen.

## Existing upstream items found

NONE VERIFIED. The duplicate check for this draft is INCOMPLETE. The GitHub connector's search returned zero results in mcu-tools/mcuboot, but the same tool returned zero in mavlink/mavlink where relevant issues demonstrably exist, so that zero is not evidence of absence. The connector then disconnected, and a WebFetch of the GitHub issue search page was not permitted in time. I therefore could not read MCUboot issues, pull requests or discussions. The earlier review (docs/REPORT_body.md section 5.2) also records that "issue and PR search was blocked, so absence is not proof". MCUboot is a likely place for an existing request, since wolfBoot, TF-M BL1 and others already have post quantum verification; check carefully. If a thread exists, convert this draft into a short comment that links it.

## What I did verify just now (files on the main branch, retrieved 2026-10-12)

- docs/design.md lists image TLV signature types RSA2048_PSS (0x20), ECDSA_SIG (0x22), RSA3072_PSS (0x23) and ED25519 (0x24), plus SHA256, SHA384 and SHA512 hash TLVs, and KEYHASH and PUBKEY TLVs. A case insensitive search of design.md, release-notes.md and imgtool.md for dilithium, ml-dsa, lms, xmss, pqc, post-quantum, quantum and hash-based found nothing. Source: https://raw.githubusercontent.com/mcu-tools/mcuboot/main/docs/design.md
- docs/imgtool.md: "This tool currently supports rsa-2048, rsa-3072, ecdsa-p256 and ed25519 keys." Source: https://raw.githubusercontent.com/mcu-tools/mcuboot/main/docs/imgtool.md
- This is documentation only; I did not search the source tree or open pull requests, so support could exist in code or a branch that the docs do not mention.

## Venue and process (retrieved now)

- No CONTRIBUTING.md and no .github issue template or config were found (404) in mcu-tools/mcuboot main.
- README (https://raw.githubusercontent.com/mcu-tools/mcuboot/main/README.md): the roadmap is "tracked using GitHub issues" and input is invited at https://github.com/mcu-tools/mcuboot/issues; the developer mailing list is https://groups.io/g/MCUBoot and there is a Discord channel (invite link in the README). Both suit a design question.
- CODE_OF_CONDUCT.md is the Contributor Covenant.
- docs/SECURITY.md: vulnerability reports go through the GitHub "Report a vulnerability" button or mcuboot-security@lists.trustedfirmware.org. This draft contains no vulnerability and must not be sent there.

Recommended venue: a GitHub issue (the README names issues as the roadmap venue), with a pointer posted to the mailing list. Text below is written for an issue.

## Title

Question: is post quantum image signature support (LMS/HSS or ML-DSA) planned or being discussed?

## Body

Hello,

I am Huda Mueen. I am preparing a sourced review of post quantum signature options for firmware verification on drone and robot computers, and I would like to describe MCUboot's position accurately. This is a question, not a feature request, and I am not asking anyone to commit to a schedule.

What I found on the main branch on 2026-10-12: the image signature TLVs documented in docs/design.md are RSA 2048 PSS, ECDSA, RSA 3072 PSS and Ed25519, and imgtool lists rsa-2048, rsa-3072, ecdsa-p256 and ed25519 keys. I did not find a post quantum signature type in the documents I read (design.md, release-notes.md, imgtool.md). I have not read the source tree, so please correct me if support exists.

Context I can cite: NIST SP 800-208 (section 1.1) says stateful hash based signatures such as LMS and XMSS suit firmware authentication on constrained devices that will be in service for decades (https://csrc.nist.gov/pubs/sp/800/208/final). Other bootloaders list post quantum verification, for example wolfBoot documents ML-DSA, LMS/HSS and XMSS and a hybrid mode (https://raw.githubusercontent.com/wolfSSL/wolfBoot/master/docs/PQ.md). Size matters for slot headers: wolfBoot's own example configuration sets a 2420 byte signature and a 4840 byte image header for ML-DSA-44, and a 2644 byte signature and 5288 byte header for a two level LMS example. These are example configuration values from its documentation, not measurements, and the two setups are not directly comparable.

My questions:

1. Is there an existing issue, pull request, mailing list thread or roadmap note about post quantum image signatures that I should read? If so, I will link it and withdraw this question.
2. If the maintainers have a view, which family is the more natural fit for the project: stateful hash based signatures (LMS/HSS), ML-DSA, or neither for now? I ask because stateful keys need careful signing side handling, while the verifier on the device is simpler.
3. Would the image TLV and header design allow a larger signature type and a second (hybrid) signature alongside a classical one, or would that need a format change?
4. Is the mailing list or this issue tracker the better place to follow any design discussion?

Thank you for your time. I will describe any reply as the view of the person who wrote it, not as an official project position, unless you tell me otherwise.

Huda Mueen

## Links

- https://github.com/mcu-tools/mcuboot
- https://raw.githubusercontent.com/mcu-tools/mcuboot/main/docs/design.md
- https://raw.githubusercontent.com/mcu-tools/mcuboot/main/docs/imgtool.md
- https://raw.githubusercontent.com/mcu-tools/mcuboot/main/README.md
- https://groups.io/g/MCUBoot
- https://csrc.nist.gov/pubs/sp/800/208/final
- https://raw.githubusercontent.com/wolfSSL/wolfBoot/master/docs/PQ.md

## Items to verify before filing

- The wolfBoot sizes (2420 / 4840 and 2644 / 5288 bytes) were recorded in data/raw/S4_migration.md on 2026-10-11 from PQ.md; re-open PQ.md and confirm they are unchanged before quoting.
- SP 800-208 section 1.1 paraphrase comes from data/raw/S4_migration.md (source A5); confirm against the PDF.
- Question 3 assumes the TLV layout allows variable length values; read boot/bootutil and docs/design.md TLV rules before asking, or drop the question.

## Pre filing checklist

- [ ] Complete the duplicate search with the connector reconnected: mcu-tools/mcuboot issues, pull requests and discussions (including closed), the groups.io archive, and the Zephyr and TF-M trackers for MCUboot related PQ items; terms: post-quantum, PQC, quantum, ML-DSA, Dilithium, ML-KEM, Kyber, LMS, XMSS, SLH-DSA, hybrid signature.
- [ ] If any match is found, replace this draft with a short comment that links it.
- [ ] Confirm the mailing list and Discord are still active and decide whether to post there first.
- [ ] Check wording: no em dashes, no hyphens between words except in names, no emojis, no affiliation, no claim of authority, 4 questions or fewer, no attack details, no side channel guidance.
- [ ] Do not use the security reporting channel.
- [ ] Huda to read and approve; nothing is posted until the author approves it.
