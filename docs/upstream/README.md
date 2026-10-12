# Upstream question drafts

All three items are DRAFT NOT FILED. Nothing was posted, commented on, reacted to or otherwise sent to any project.

| Project | Existing issues found (links) | Venue | Status | Checks done |
|---|---|---|---|---|
| MAVLink (mavlink/mavlink, mavlink/mavlink-devguide) | Question already answered upstream. https://github.com/mavlink/mavlink/issues/2525 (closed 2026-06-30: no PQC roadmap, not thought necessary, use a secure transport). https://github.com/mavlink/mavlink/issues/2527 (closed 2026-06-24: third party PQC wire format proposal, maintainers want existing extension mechanisms). Adjacent, not PQC: https://github.com/mavlink/mavlink/issues/2571 (open, Ed25519 arm authorization credential). | GitHub issues, Discord #mavlink-general, mailing list, RFCs via mavlink/rfcs pull request (per devguide contributing page) | DRAFT NOT FILED. Draft is a short optional comment for #2525; recommendation is to post nothing unless there is something new | Read #2525, #2527, #2571 and all their comments; listed the 10 newest issues; read contributing guide. NOT done: full issue list (682 issues), pull requests, discussions, mavlink/rfcs, devguide tracker, dev meeting wiki |
| SROS2 / DDS-Security (ros2/sros2, ROS Discourse, eProsima Fast-DDS) | None verified. Search incomplete. | ROS Discourse question post (ros2 org routes feature discussion there; Zulip for developer chat; Robotics Stack Exchange for usage questions); sros2 issue only if asked | DRAFT NOT FILED | Read sros2 CONTRIBUTING and README, ros2 org issue routing, Fast-DDS issue config. Connector search returned zero but is shown unreliable. NOT done: any issue, PR, discussion or Discourse search; Fast-DDS "Issues and Support" section; ROS design norms |
| MCUboot (mcu-tools/mcuboot) | None verified. Search incomplete. | GitHub issue (README names issues as the roadmap venue) plus developer mailing list (groups.io) or Discord | DRAFT NOT FILED | Re-read design.md, imgtool.md, release-notes.md, README, SECURITY.md, CODE_OF_CONDUCT.md on main: no PQ signature type documented. Connector search returned zero but is shown unreliable. NOT done: any issue, PR, discussion or mailing list archive search; source tree search |

## Summary of existing issues found

- MAVLink has already addressed the question. #2525 (opened 2026-06-16 by a third party) asked whether MAVLink has a PQC roadmap. A maintainer said there is none, and on 2026-06-30 the closing comment said the project does not think it needs one, that signature data collected now is not a harvest risk, that current controllers are unlikely to have the processing capability, that carrying 4627 bytes per message is not acceptable, and that the advice would be a secure transport. #2527 (an RFC for a custom message carrying ML-DSA-87 and ML-KEM-1024 material) was closed after a maintainer said anything outside the existing extension mechanisms would not be of interest. A new question issue would be a duplicate and, given the tone of the earlier thread, could be received poorly; hence the comment only draft.
- #2571 is open and relates to signed authorization credentials, not PQC.
- For SROS2/DDS-Security and MCUboot nothing is confirmed either way because search could not be completed.

## Important caveats

1. The GitHub connector's issue search returned zero results for "post-quantum cryptography" and "quantum" in mavlink/mavlink even though #2525 and #2527 exist. Treat every zero from that tool as meaningless. Existing issues were only found by reading known numbers and listing recent issues.
2. The GitHub connector disconnected mid task, the `gh` CLI was refused for these repositories, the public search API returned 403, and a WebFetch of GitHub search pages was not permitted. I did not use add_repo to widen access, because that attaches credentials and was not requested. Raw files on raw.githubusercontent.com were readable and were used for contribution guidance.
3. Second consequence for the main report: data/raw/S3_robotics.md and docs/REPORT_body.md section 5.1 say mavlink #2527 was "not retrievable". It is retrievable, and the maintainer position in #2525 is a citable fact. The report has not been edited.
4. Facts in drafts come only from data/raw/S3_robotics.md, data/raw/S4_migration.md, docs/REPORT_body.md, data/evidence.csv row S2-0407, and pages retrieved on 2026-10-11 or 2026-10-12, each cited with a URL. docs/PREDICTIONS*.md was not read. Items needing re verification are listed at the foot of each draft.

## To finish before anything is filed

1. Reconnect the GitHub connector (or run the searches by hand) and complete the checklist in each draft, with terms: post-quantum, PQC, quantum, ML-DSA, Dilithium, ML-KEM, Kyber, LMS, XMSS, SLH-DSA, hybrid signature.
2. Re run the style check: no em dashes, no hyphens between words except in names, no emojis, no affiliation, no claim of authority.
3. Huda reads, edits and approves each text herself.
