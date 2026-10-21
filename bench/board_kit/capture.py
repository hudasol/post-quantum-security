#!/usr/bin/env python3
"""Capture board output (UART through the ST-LINK virtual COM port) to a raw log with timestamps.

Author: Huda Mueen. Uses pyserial (free) for a real board. For dry runs it also accepts an existing
log file (--replay) or a stream on standard input (--stdin), for example QEMU output piped in.

Raw log format (text, one record per line):
  # capture,<key>,<value>            header written before any board output
  <UTC ISO 8601 timestamp><TAB><line exactly as received, without the line ending>
  # capture,end,<reason>             footer: marker (pqm4 end marker '#'), timeout, eof or max_lines

The header carries the run (power cycle number), image name, experiment and evidence label, so
the firmware never has to be rebuilt per power cycle. parse.py reads this format.

Examples:
  python3 capture.py --port /dev/ttyACM0 --baud 38400 --board NUCLEO-L4R5ZI --run 1 --image <name> \
      --experiment B0 --label "board measured" --echo --out logs/run1_<name>.log
  qemu-system-arm ... | python3 capture.py --stdin --board "QEMU mps2-an386" --run 1 --image <name> \
      --label emulated --out x.log
  python3 capture.py --replay old_output.txt --board "QEMU mps2-an386" --run 1 --image <name> \
      --label emulated --out x.log

--board is required (no default), so logs of the Cortex-M4 and Cortex-M33 boards can never share a
board name by accident; parse.py also checks it against the META platform line of B1 images.
--echo prints each line on the screen as it arrives, so the person at the bench can see which
operation is running (needed to read the meter per operation phase, ONE_AFTERNOON.md).
"""
import argparse
import datetime as _dt
import sys
import time

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit_config as K  # noqa: E402

END_MARKER = "#"  # pqm4 speed, stack and test binaries end with hal_send_str("#")
LABELS = ("board measured", "emulated")
BAUD_PQM4 = 38400  # SERIAL_BAUD in pqm4 common/hal-opencm3.c at the pinned commit


def utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def header_lines(meta):
    return [f"# capture,{k},{v}" for k, v in meta.items()]


def capture_lines(lines, out, meta, clock=utc_now, stop_on_marker=True, max_lines=None,
                  deadline=None, monotonic=time.monotonic, echo=None):
    """Write header, then each incoming line with a timestamp, then a footer.

    `lines` is any iterable of str or bytes; returns (count, end_reason)."""
    for h in header_lines(meta):
        out.write(h + "\n")
    n = 0
    reason = "eof"
    for raw in lines:
        if isinstance(raw, bytes):
            raw = raw.decode("ascii", errors="replace")
        line = raw.rstrip("\r\n")
        if line == "" and raw == "":
            if deadline is not None and monotonic() > deadline:
                reason = "timeout"
                break
            continue
        ts = clock()
        out.write(f"{ts}\t{line}\n")
        if echo is not None:
            echo.write(f"{ts}  {line}\n")
            echo.flush()
        n += 1
        if stop_on_marker and line.strip() == END_MARKER:
            reason = "marker"
            break
        if max_lines is not None and n >= max_lines:
            reason = "max_lines"
            break
        if deadline is not None and monotonic() > deadline:
            reason = "timeout"
            break
    out.write(f"# capture,end,{reason}\n")
    out.flush()
    return n, reason


def serial_lines(port, baud, read_timeout=1.0):
    """Yield lines from a serial port; yields '' on read timeouts so the caller can stop."""
    import serial  # pyserial, imported only for real captures
    with serial.Serial(port, baud, timeout=read_timeout) as s:
        s.reset_input_buffer()
        while True:
            yield s.readline()


def build_meta(a, source):
    return {"version": "1", "source": source, "start_utc": utc_now(), "experiment": a.experiment,
            "image": a.image, "run": a.run, "label": a.label, "board": a.board,
            "note": a.note or ""}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--port", help="serial device, for example /dev/ttyACM0 or COM5")
    src.add_argument("--replay", help="existing text log to replay (dry run)")
    src.add_argument("--stdin", action="store_true", help="read lines from standard input")
    ap.add_argument("--baud", type=int, default=BAUD_PQM4)
    ap.add_argument("--run", type=int, required=True, help="power cycle number (1, 2, 3)")
    ap.add_argument("--image", required=True, help="image name that was flashed")
    ap.add_argument("--experiment", choices=("B0", "B1"), default="B0")
    ap.add_argument("--label", choices=LABELS, required=True)
    ap.add_argument("--board", required=True, choices=sorted(K.BOARD_NAMES.values()),
                    help="board name written to the log header; required, no default")
    ap.add_argument("--echo", action="store_true", help="also print each line as it arrives")
    ap.add_argument("--note", default="")
    ap.add_argument("--timeout", type=float, default=3600.0, help="seconds before giving up")
    ap.add_argument("--max-lines", type=int, default=None)
    ap.add_argument("--no-marker-stop", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.port:
        lines, source = serial_lines(a.port, a.baud), f"serial:{a.port}@{a.baud}"
    elif a.replay:
        lines, source = open(a.replay, "rb"), f"replay:{a.replay}"
    else:
        lines, source = sys.stdin.buffer, "stdin"
    try:
        with open(a.out, "w", encoding="ascii", errors="replace") as out:
            n, reason = capture_lines(lines, out, build_meta(a, source),
                                      stop_on_marker=not a.no_marker_stop, max_lines=a.max_lines,
                                      deadline=time.monotonic() + a.timeout,
                                      echo=sys.stdout if a.echo else None)
    finally:
        if hasattr(lines, "close") and a.replay:
            lines.close()
    print(f"captured {n} lines, end={reason}, file={a.out}")
    return 0 if reason in ("marker", "eof", "max_lines") else 1


if __name__ == "__main__":
    sys.exit(main())
