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
  python3 capture.py --port /dev/ttyACM0 --baud 38400 --run 1 --image <name> --experiment B0 \
      --label "board measured" --out logs/run1_<name>.log
  qemu-system-arm ... | python3 capture.py --stdin --run 1 --image <name> --label emulated --out x.log
  python3 capture.py --replay old_output.txt --run 1 --image <name> --label emulated --out x.log
"""
import argparse
import datetime as _dt
import sys
import time

END_MARKER = "#"  # pqm4 speed, stack and test binaries end with hal_send_str("#")
LABELS = ("board measured", "emulated")
BAUD_PQM4 = 38400  # SERIAL_BAUD in pqm4 common/hal-opencm3.c at the pinned commit


def utc_now():
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def header_lines(meta):
    return [f"# capture,{k},{v}" for k, v in meta.items()]


def capture_lines(lines, out, meta, clock=utc_now, stop_on_marker=True, max_lines=None,
                  deadline=None, monotonic=time.monotonic):
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
        out.write(f"{clock()}\t{line}\n")
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
    ap.add_argument("--board", default="NUCLEO-L4R5ZI")
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
                                      deadline=time.monotonic() + a.timeout)
    finally:
        if hasattr(lines, "close") and a.replay:
            lines.close()
    print(f"captured {n} lines, end={reason}, file={a.out}")
    return 0 if reason in ("marker", "eof", "max_lines") else 1


if __name__ == "__main__":
    sys.exit(main())
