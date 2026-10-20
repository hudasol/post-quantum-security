# S12 Policy timeline: retrieval log (raw notes)

Author of review: Huda Mueen. Date of this pass: 2026-10-20. Output: `data/policy_timeline.csv`, rendered to `docs/POLICY_TIMELINE.md` by `planner/policy_timeline.py`.

Method: rows that earlier passes already hold as retrieved facts are reused and cited by row (`data/raw/S1_standards.md`, retrieved 2026-10-11; `data/raw/S11_standards_recheck.md`, retrieved 2026-10-17; `data/raw/S10_cnsa_faq.md`, supplied PDF read 2026-10-16). This pass made one new web fetch for NIST IR 8547 status, one fetch attempt for Australia ASD, and read the two supplied UAE PDFs. No curl, mirror, cache or archive was used. Paraphrases only.

## 1. New retrievals in this pass

| # | Item | Source | Location | Finding (paraphrase) | Status |
|---|---|---|---|---|---|
| 1 | NIST IR 8547 status | https://csrc.nist.gov/pubs/ir/8547/ipd (web fetch, 2026-10-20) | page header; Document History | Still labelled Initial Public Draft, published 2024-11-12; comments closed 2025-01-10; planning note of 2025-01-21 says the comments are posted; the history lists only the 2024-11-12 draft; no link to a later version. | draft, IN FLUX |
| 2 | NIST IR 8547 search | web search, 2026-10-20 | result list | Results point only to the initial public draft and its announcement; no final version found. | draft |
| 3 | Australia ASD planning page | https://www.cyber.gov.au/business-government/secure-design/quantum/planning-for-post-quantum-cryptography (web fetch, 2026-10-20, one attempt as the brief requires) | none | Refused by the site's robots rules. Not retried and not worked around. The ASD row stays a 2026-10-11 summary (S1 row 51) and is marked unverified. | NOT RETRIEVED, IN FLUX |
| 4 | UAE National Encryption Policy Version 1.0, Cyber Security Council (supplied PDF, 51 pages, text layer) | `UAE National Encryption Policy - Cyber Security Council.pdf` | version control page; section 6.1 (printed p. 36); section 7 (printed p. 38); section 8 | Version 1.0, September 2025, first release, prepared by CSC, classification open. Section 6 (post quantum cryptography) has the objective of preparing entities to protect non open information against future quantum threats and six duties: inventory of systems using public key cryptography; lab testing before production; a transition plan with 'Independence analysis' (order of system transition), decommissioning and product validation; PQC acquisition policies (service levels, vendor surveys); alerting IT departments and vendors; workforce education. No date or deadline is attached to any of them. Section 7: compliance is monitored through the UAE IA Standard controls and reported on the National Cyber Index Platform. | final, no dated milestone |
| 5 | UAE legislation portal entry (supplied PDF, 7 pages, scanned print of the web page dated 10/12/26 in the print header) | `Public Policy Document National Encryption Policy - uaelegislation.gov.ae.pdf` | pp. 1 to 7 (text read by OCR of the rendered pages) | Entry for the National Encryption Policy by the Cyber Security Council, sector Telecommunication, Technology and Space, dated 17 Sep 2025 (the year digits are partly obscured in the scan). The summary says the policy gives mandatory encryption controls for data at rest and in motion, sets key management requirements and paves the way for quantum safe computing; components listed include governance, data at rest, data in motion, key management and post quantum cryptography general requirements; audience includes federal and emirate government entities and CII entities, with emirate CIIP programmes leading where they exist. No PQC dates. | final, no dated milestone |

## 2. Rows reused from earlier passes

| Timeline rows | Raw file and rows | Retrieved |
|---|---|---|
| P01, P02 | S1 rows 14, 15, 17 | 2026-10-11 (P01 status rechecked 2026-10-20) |
| P03 to P07 | S10 rows 22 to 26 (supplied CNSA 2.0 FAQ, Ver. 2.1, December 2024) | 2026-10-16 |
| P08 to P10 | S1 rows 37 to 39 | 2026-10-11 |
| P11 to P13 | S1 row 33 | 2026-10-11 |
| P14 | S11 row 13 | 2026-10-17 |
| P15 | S1 rows 47, 48 | 2026-10-11 |
| P16 to P19 | S11 rows 1 to 3 | 2026-10-17 |
| P20 to P22 | S11 rows 6 to 9 | 2026-10-17 |
| P23 | S1 row 51 (summary only), S11 row 16 | 2026-10-11 (not read in full) |

## 3. Gaps

1. Australia: no full reading of the ASD page in any pass; the 2030 date is unverified.
2. UAE: neither supplied document gives a PQC date. The 2025-11-27 report of an approved executive regulation and transition plans (S1 row 62) is a wire report; the regulation text was not retrieved.
3. The NCSC and EU rows were not refetched in this pass; they rest on the 2026-10-11 retrieval.
4. Germany and France give no migration end date on the pages read.
