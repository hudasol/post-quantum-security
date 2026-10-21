# Third look reading rules (verification 5, wording fields)

Author: Huda Mueen.

1. You see a row id, a field name, the source and a location. Open the source and go to the location.
2. Write in `value_as_in_source` what the source says for that field at that location, copied as printed
   (same words, same capitals, same symbols). Do not shorten, translate or normalise.
3. Field meanings: scheme (algorithm family named by the source), parameter_set (parameter set or
   variant name), operation (keygen, encaps, decaps, sign, verify or the operation name printed),
   device (board or chip), core (processor core), clock_mhz (clock in MHz), library (code base or
   implementation name), quantity (what a fact measures), unit, conditions (conditions printed with the value).
4. If the value is not at the stated location but elsewhere in the same source, copy it and write where
   in `location_found` (page, table, section). If it is nowhere in the source, leave `value_as_in_source`
   blank and write `not in source` in `note`. If the source is ambiguous, copy the candidates and write
   `ambiguous` in `note`.
5. Do not look at any other sheet, staging file or reader file of this repository. Use only the source.
6. If a source cannot be retrieved, leave the line blank and write `not retrieved` and the reason in `note`.
   Do not use mirrors, caches or archives.
7. Output: `third_look_<n>.csv` next to the sheet, columns id, field, value_as_in_source, location_found, note,
   one line per sheet line.
