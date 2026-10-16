# MAVLink upstream draft: comment suggestion (NOT a new issue)

Status: DRAFT NOT FILED. Nothing has been posted, commented on or reacted to.
Author of the eventual text: Huda Mueen.

## Recommendation

Do not open a new issue. The question "does MAVLink have a post quantum plan?" has already been asked and answered upstream. If anything is posted, it should be a short, optional follow up that links the existing thread. If there is nothing new to add, post nothing.

## Existing upstream items found (read directly through the GitHub connector, 2026-10-11/12)

| Item | State | Date | One line paraphrase |
|---|---|---|---|
| https://github.com/mavlink/mavlink/issues/2525 "Post-quantum authenticated COMMAND_LONG / SET_POSITION_TARGET, does MAVLink have a PQC roadmap?" | closed (completed) | opened 2026-06-16, closed 2026-06-30 | Asks directly for a PQC roadmap. A maintainer replied on 2026-06-17 that there is no PQC roadmap and that MAVLink offers signing only, no encryption; the 2026-06-30 closing comment, after the 2026-07-01 dev meeting notes were linked, says the project has no post quantum roadmap and does not think it needs one, that collected signatures are not a harvest risk, that current controllers are unlikely to have the processing capability, that nobody wants to carry 4627 bytes per message, and that the advice would be to use a secure transport. |
| https://github.com/mavlink/mavlink/issues/2527 "RFC: Post-Quantum Authentication for MAVLink v2, relay-transparent wire format (CLEITONQ_CHUNK)" | closed (completed) | opened 2026-06-20, closed 2026-06-24 | A third party proposes a custom message (ID 50000) carrying ML-DSA-87 and ML-KEM-1024 material in fragments. A maintainer replied that the project would not be interested in anything that does not use its existing extension mechanisms (an incompatibility flag). |
| https://github.com/mavlink/mavlink/issues/2571 "Proposal: MAV_TUNNEL_PAYLOAD_TYPE value for command authorization credentials" | open | opened 2026-08-14, last comment 2026-09-16 | Not post quantum. A signed arm authorization credential (Ed25519 in the proposal text) is discussed; maintainers declined a TUNNEL type and are considering a dedicated message. Adjacent only: a credential format identifier could in principle allow a later algorithm change, but nobody in the thread says so. |
| ArduPilot Discourse thread, "Post-quantum authentication for MAVLink C2" https://discuss.ardupilot.org/t/post-quantum-authentication-for-mavlink-c2-found-a-relay-problem-nobody-talks-about/144270 | not re-checked | posted 2026-06-20 | Same third party as #2527 (recorded in data/raw/S3_robotics.md section 1.4). |

Not found by me: any issue, discussion or PR in mavlink/mavlink or mavlink/mavlink-devguide beyond the above. See the completeness caveat below.

Note on this repository: data/raw/S3_robotics.md recorded #2527 as "not retrievable, 403". It is retrievable now. docs/REPORT_body.md section 5.1 should cite #2525 and #2527 and the maintainer position when the report is next revised. This draft does not edit the report.

## Completeness caveat (important)

The connector's issue search returned zero results for "post-quantum cryptography" and "quantum" even though #2525 and #2527 exist, so it cannot be trusted for absence claims. I found the items above by reading known issue numbers and by listing the 10 most recently created issues. I did NOT page through all 682 issues, did NOT check pull requests, discussions, the mavlink/rfcs repository, the mavlink-devguide issue tracker or the dev meeting wiki pages. The connector then disconnected. Those checks must be completed before any posting.

## Venue and process (from https://raw.githubusercontent.com/mavlink/mavlink-devguide/master/en/contributing/contributing.md)

- Specification and message changes go through pull requests to mavlink/mavlink; complex changes need an RFC pull request in mavlink/rfcs.
- To raise awareness the guide points to Discord (#mavlink-general) and the MAVLink mailing list (Google Groups).
- No CODE_OF_CONDUCT.md and no issue template were found at the expected paths in mavlink/mavlink (404 on raw.githubusercontent.com). I did not check the organisation level .github repository by another route.
- Maintainers state that they are busy and interrupt driven (comment on #2571, 2026-09-16), and a participant in #2525 reacted strongly to what looked like promotional or machine generated text. Keep any post short, plain and specific.

## Optional comment text (for #2525, only if the pre filing checklist passes)

Title: none (comment)

Body:

> Thank you for the clear answer in this thread, and for linking the dev meeting notes. I have read #2525 and #2527 so as not to repeat them.
>
> I have two small follow up questions, and I understand if the answer is simply that they are out of scope.
>
> 1. Would the project welcome a documentation pull request to the developer guide that records the current position in one place: signing is symmetric and provides authentication only, there is no encryption, and a secure transport is the suggested route where long term confidentiality matters?
> 2. The signing key is shared by all parties and is provisioned out of band or with SETUP_SIGNING over a secure link such as USB. Is guidance on provisioning something you would want in the guide, or is it considered a deployment matter?
>
> My own interest is a sourced review of post quantum migration for drone computers. I am not proposing a protocol change. Thank you for your time.
>
> Huda Mueen

Facts behind the questions (all from this repository's retrieved sources): the signature field is 13 bytes with a 6 byte tag, the key is 32 bytes and shared (https://mavlink.io/en/guide/message_signing.html, retrieved 2026-10-11, data/raw/S3_robotics.md section 1.1); maximum payload 255 bytes (https://mavlink.io/en/guide/serialization.html); ML-DSA-44 signature 2420 bytes (FIPS 204 Table 2, https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.204.pdf, evidence row S2-0407).

## Links

- https://github.com/mavlink/mavlink/issues/2525
- https://github.com/mavlink/mavlink/issues/2527
- https://github.com/mavlink/mavlink/issues/2571
- https://github.com/mavlink/mavlink-devguide/blob/master/en/contributing/contributing.md
- https://mavlink.io/en/guide/message_signing.html

## Pre filing checklist

- [ ] Decide whether there is anything new at all; if not, do not post.
- [ ] Complete the search: page all mavlink/mavlink issues, pull requests and discussions, mavlink/rfcs, mavlink/mavlink-devguide issues and PRs, and the dev meeting wiki pages, for: post-quantum, PQC, quantum, ML-DSA, Dilithium, ML-KEM, Kyber, LMS, XMSS, SLH-DSA, hybrid signature.
- [ ] Re-read #2525 and #2527 for comments added after 2026-10-12.
- [ ] Confirm question 1 is not already covered by the current devguide text (read https://mavlink.io/en/guide/message_signing.html again).
- [ ] Prefer a documentation pull request to a comment on a closed issue if the maintainers' answer to question 1 is yes.
- [ ] Check wording: no em dashes, no hyphens between words except in names, no emojis, no affiliation, no claim of authority, no benchmark numbers from third parties.
- [ ] Huda to read the final text and approve; nothing is posted until the author approves it.
