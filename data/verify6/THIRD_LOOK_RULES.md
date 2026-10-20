# Third look rules for verification 6 (stream S13)

Author: Huda Mueen.

The third reader gets only `data/verify6/third_look_queue.csv` (row id, field, kind, source title, source URL, location) and these rules. The staged values and the first two readers' values are not shown.

1. Work alone. Do not open any other file under `data/verify6/` or `data/raw/`.
2. Retrieve each source yourself from `source_url` (curl, or a web fetch tool if curl is refused). Do not use mirrors, caches or archives.
3. At `location_in_source`, read the single field named in `field` (scheme, parameter_set, operation, device, core, clock_mhz, library, cycles, ram_bytes, stack_bytes, flash_or_code_bytes, energy_uj, key_or_sig_size_bytes). For wording fields write the words the source uses (table row or column label, caption or setup sentence the table refers to). For numbers write plain integers or decimals; convert printed thousands (k, kilo cycles) to units and say so in the note.
4. Write `data/verify6/third_look.csv` with columns `id,field,third_value,status,note`, one line per queue line. `status` is `found`, `not_in_source` (the field is not stated at or near the location) or `ambiguous_source` (two candidate cells, a printing defect, unclear labels). Leave `third_value` blank unless status is `found`.
