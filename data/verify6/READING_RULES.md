# Reading rules for verification 6 (stream S13)

Author: Huda Mueen.

These rules are given to each reader together with the blank sheet `data/verify6/sheet_rows.csv`. They are the rules of round 4 (verification 5), unchanged except for the file names.

1. Work alone. Do not open `data/raw/S13_staged.csv`, `data/raw/S13_verified.csv`, the other reader's sheet, or any file under `data/verify6/` other than the blank sheet and these rules.
2. For every row, retrieve the source yourself from `source_url` (curl, or a web fetch tool if a site refuses curl). If a source cannot be retrieved, leave the row blank and write "not retrieved" and the reason in `reader_note`. Do not use mirrors, caches or archives.
3. Go to `location_in_source` (table, row, column, page or line). Fill in the fields you can read at that location, or in the caption, header or the setup paragraph the table refers to: scheme, parameter_set, operation, device, core, clock_mhz, library, cycles, ram_bytes, stack_bytes, flash_or_code_bytes, energy_uj, key_or_sig_size_bytes.
4. Write numbers as plain integers or decimals without separators. If the source prints a value in thousands (k, kilo cycles, KCCs) or in KB, convert to cycles or bytes and say so in `reader_note` (for example "printed 760 KCCs, x1000"). If the location gives a value in a unit that has no column (milliseconds, KB with a decimal), leave the column blank and quote the printed value in `reader_note`.
5. Leave a field blank when the source does not state it at or near the location. Do not infer, compute or guess a value. A blank is not an error.
6. If the location is ambiguous (two candidate cells, a printing defect, a footnote marker fused with a number), fill nothing for that field and describe the problem in `reader_note`.
7. Save your sheet as `data/verify6/reader1_rows.csv` or `data/verify6/reader2_rows.csv` with the same columns and the same row order as the blank sheet.
