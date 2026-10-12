# Supplier question pack

Author: Huda Mueen. This pack contains a neutral email template, a response tracking sheet (`response_tracker.csv`) and a short lab loan request. It makes no claim about any supplier. Fill the tracker only with what a supplier writes, and keep the supplier's own document reference for every answer.

## Email template (chip and board suppliers)

Subject: Question about updatable boot verification and post quantum roadmap for [product name]

Dear [name or team],

I am an undergraduate researcher studying how fielded drones and robots can move to post quantum signatures for firmware. I would be grateful for a short factual answer to the questions below for [product or part number]. If the information is only available under a non disclosure agreement, please tell me and I will treat the question as closed.

1. Is the boot ROM signature verifier fixed in silicon, or can it be updated after shipping? If it can be updated, by what mechanism?
2. Is the trust anchor (a public key or a key hash) stored in fuses or one time programmable memory? Can a second key, a second algorithm or a replacement be provisioned after the first one is programmed?
3. Does the part support, or does your roadmap include, verification of ML-DSA, LMS or XMSS signatures at boot, in hardware or in an updatable first stage? Please indicate a public document or date range if you can share one.
4. Does the part include a hardware accelerator for ML-KEM or ML-DSA, and if so, which document describes its interface?
5. Is there a public security advisory or product change notice process through which a change to the boot verifier would be announced?

Please reply with document names or links where possible, so that I can cite the source exactly. I will not publish any answer without your permission if it is marked confidential.

Kind regards,
Huda Mueen
[email address]

Notes for sending: send from your own address, one email per supplier, and do not attach this repository's report unless you want to. Do not state or imply any claim about the supplier's product in the email.

## Lab loan request (for borrowed hardware)

Subject: Request to borrow a Cortex M4F or M33 board for a few hours

Dear [name],

I am running a small benchmark of post quantum signature verification on microcontrollers (public libraries, no production use). I need a few hours on a Cortex M4F or Cortex M33 development board, with a USB cable and a computer I can flash from. I will bring the firmware prepared and leave the results with the lab if useful. Would that be possible, and who should I contact to arrange a time?

Kind regards,
Huda Mueen

## Tracker columns

See `response_tracker.csv`. Status values: not sent, sent, answered, declined, needs NDA. The answer columns accept only `yes`, `no`, `not stated` or `under NDA`, with the supplier's document reference in the next column.
