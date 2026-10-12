#!/usr/bin/env python3
"""Generate a SYNTHETIC current trace to test analyze_power.py. Not data about any real device.
Known truth: idle 10 mA, active 25 mA, window of D ms, so net energy/op = V*(25-10)mA*D (exactly known)."""
import argparse, random

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--volts", type=float, default=3.3)
ap.add_argument("--rate", type=float, default=100000.0, help="samples per second")
ap.add_argument("--window-ms", type=float, default=8.0)
ap.add_argument("--gap-ms", type=float, default=20.0)
ap.add_argument("--n", type=int, default=50)
ap.add_argument("--noise-ma", type=float, default=0.3)
ap.add_argument("--seed", type=int, default=1)
a = ap.parse_args()
rng = random.Random(a.seed)
dt = 1.0 / a.rate
t = 0.0
with open(a.out, "w") as fh:
    fh.write("time_s,current_a,marker\n")
    def seg(ms, cur, mk):
        global t
        for _ in range(int(ms / 1000.0 * a.rate)):
            fh.write(f"{t:.7f},{(cur + rng.gauss(0, a.noise_ma)) / 1000.0:.7f},{mk}\n")
            t += dt
    seg(a.gap_ms, 10.0, 0)
    for _ in range(a.n):
        seg(a.window_ms, 25.0, 1)
        seg(a.gap_ms, 10.0, 0)
print(f"expected net energy/op = {a.volts * (25.0 - 10.0) / 1000.0 * a.window_ms / 1000.0 * 1e6:.3f} uJ ; "
      f"expected gross = {a.volts * 25.0 / 1000.0 * a.window_ms / 1000.0 * 1e6:.3f} uJ")
