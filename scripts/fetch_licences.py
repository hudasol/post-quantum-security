#!/usr/bin/env python3
"""Record the licence of every third party library used by the benchmark scripts.

Reads the licence file of each library at its pinned commit from raw.githubusercontent.com
(no library code is downloaded into this repository) and writes data/third_party_licences.csv.
The `licence_as_read` column is a keyword match on the retrieved file, not legal advice.
"""
import csv, hashlib, re, sys, urllib.request, datetime
LIBS = [
 ("mlkem-native","pq-code-package/mlkem-native","d1b2fe782888bdb761a50336012923180be7f502","E1 ML-KEM benchmark"),
 ("mldsa-native","pq-code-package/mldsa-native","834a90d5e846ffa1e1611bd24e160bb2e9b86d35","E1 ML-DSA benchmark"),
 ("wolfSSL","wolfSSL/wolfssl","3c5eead44904df64e6a5a1f4ebdce377d35a849a","E2 hash based signature verification"),
 ("wolfBoot","wolfSSL/wolfBoot","eb710fe1656f20addb736b5c205f18bf53fa2998","E4 boot time"),
 ("TF-PSA-Crypto","Mbed-TLS/TF-PSA-Crypto","73c5da561c8e5253db7b1fb440eda86fde8d8024","E2 comparison"),
 ("pqm4","mupq/pqm4","5e5cc76d0b072ee7077e58afcbc619a1a67a53b4","reference rows only"),
 ("slhdsa-c","pq-code-package/slhdsa-c","174c02e42257f95c210963272877c49dbb50070f","SLH-DSA cross check"),
 ("liboqs","open-quantum-safe/liboqs","5a1a854b0dc9f2141bdc771c555ee60c37950183","host measurements"),
]
NAMES = ["LICENSE","LICENSE.md","LICENSE.txt","COPYING","LICENSE-APACHE","LICENSE-MIT"]
PATTERNS = [("Apache-2.0",r"Apache License\s+Version 2\.0"),("GPL-3.0",r"GNU GENERAL PUBLIC LICENSE\s+Version 3"),
            ("GPL-2.0",r"GNU GENERAL PUBLIC LICENSE\s+Version 2"),("MIT",r"Permission is hereby granted, free of charge"),
            ("ISC",r"Permission to use, copy, modify, and/or distribute this software for any purpose"),("CC0",r"CC0 1\.0|Creative Commons Zero")]
def get(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as r: return r.read().decode("utf-8","replace")
    except Exception: return None
rows = []
for name, repo, commit, role in LIBS:
    found = []
    for n in NAMES:
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{n}"
        t = get(url)
        if t is None: continue
        ids = [k for k,p in PATTERNS if re.search(p, t, re.I|re.S)]
        found.append((n, url, ids or ["unrecognised"], hashlib.sha256(t.encode()).hexdigest()[:16]))
    if not found: found = [("(none found at root)", "", ["not retrieved"], "")]
    for n, url, ids, h in found:
        rows.append(dict(component=name, role=role, repo=f"https://github.com/{repo}", pinned_commit=commit, licence_file=n,
                         licence_file_url=url, licence_as_read="; ".join(ids), file_sha256_16=h,
                         committed_to_this_repository="no (downloaded by script, ignored by git)" if name!="liboqs" and name!="pqm4" else "no (cloned at run time)",
                         retrieved=datetime.date.today().isoformat()))
w = csv.DictWriter(open("data/third_party_licences.csv","w",newline=""), fieldnames=list(rows[0]))
w.writeheader(); w.writerows(rows)
for r in rows: print(r["component"], r["licence_file"], r["licence_as_read"])
