#!/usr/bin/env python3
import sys
import time
import argparse
import serial
from serial.tools import list_ports
import math
import re

DEFAULT_BAUD = 115200

def pick_port(explicit: str | None) -> str:
    if explicit:
        return explicit

    # Prefer stable /dev/serial/by-id/* if present
    ports = list(list_ports.comports())
    by_id = []
    for p in ports:
        if p.device.startswith("/dev/serial/by-id/"):
            by_id.append(p.device)
    if by_id:
        return by_id[0]

    # Fall back to common names
    for p in ports:
        if "ttyUSB" in p.device or "ttyACM" in p.device:
            return p.device

    raise SystemExit("No serial ports found. Pass --port /dev/ttyUSB0 (or /dev/ttyACM0).")

def open_ser(port: str, baud: int) -> serial.Serial:
    ser = serial.Serial(port, baud, timeout=0.2, write_timeout=0.5)
    # Give USB-serial devices time to settle
    time.sleep(0.4)
    ser.reset_input_buffer()
    return ser

def send_cmd(ser: serial.Serial, cmd: str, settle_s: float = 0.15, max_wait_s: float = 1.2) -> str:
    """
    Sends an AT command with CRLF and reads until we see OK/ERR or we time out.
    Handles multi-line responses and devices that don't end lines cleanly.
    """
    wire = (cmd.strip() + "\r\n").encode("utf-8")
    ser.reset_input_buffer()
    ser.write(wire)
    ser.flush()
    time.sleep(settle_s)

    deadline = time.time() + max_wait_s
    buf = bytearray()
    saw_terminal = False

    while time.time() < deadline:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            text = buf.decode(errors="replace")
            # Most BU03 responses terminate with OK or ERR on its own line
            if "\nOK" in text or "\rOK" in text or text.strip().endswith("OK"):
                saw_terminal = True
                break
            if "\nERR" in text or "\rERR" in text or text.strip().endswith("ERR"):
                saw_terminal = True
                break
        else:
            time.sleep(0.02)

    # One last small drain
    time.sleep(0.05)
    n = ser.in_waiting
    if n:
        buf += ser.read(n)

    out = buf.decode(errors="replace")
    if not out and not saw_terminal:
        out = "(no response)"
    return out.strip("\x00")

def interactive(ser: serial.Serial):
    print("BU03 AT CLI. Type commands like: AT+GETCFG  (Ctrl-C to quit)")
    while True:
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not cmd:
            continue
        resp = send_cmd(ser, cmd, max_wait_s=2.0)
        print(resp)
        print()

def distance_loop(ser: serial.Serial, period: float):
    print("Polling AT+DISTANCE (Ctrl-C to stop).")
    while True:
        try:
            resp = send_cmd(ser, "AT+DISTANCE", settle_s=0.05, max_wait_s=1.0)
            # print raw response; you can parse if needed
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] {resp}")
            time.sleep(period)
        except KeyboardInterrupt:
            print()
            return

def quick_probe(ser: serial.Serial):
    cmds = ["AT", "AT+GETVER", "AT+GETCFG", "AT+GETDEV"]
    for c in cmds:
        print(f"==> {c}")
        print(send_cmd(ser, c, max_wait_s=2.0))
        print()

def main():
    ap = argparse.ArgumentParser(description="BU03 serial/AT helper")
    ap.add_argument("--port", help="Serial port, e.g. /dev/ttyUSB0 or /dev/serial/by-id/...")
    ap.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    ap.add_argument("--probe", action="store_true", help="Run AT/GETVER/GETCFG/GETDEV and exit")
    ap.add_argument("--distance", action="store_true", help="Poll AT+DISTANCE repeatedly")
    ap.add_argument("--period", type=float, default=0.5, help="Seconds between distance polls")
    ap.add_argument("--calibrate", action="store_true", help="Interactive linear calibration using AT+DISTANCE")
    ap.add_argument("--points", type=int, default=3, help="Number of calibration points (N)")
    ap.add_argument("--samples", type=int, default=10, help="Samples per point (filters 0.000000)")
    args = ap.parse_args()

    port = pick_port(args.port)
    print(f"Using port: {port} @ {args.baud}")
    ser = open_ser(port, args.baud)

    try:
        if args.calibrate:
            id_number = int(input("Enter ID number: "))
            calibrate_mode(id_number=id_number, ser=ser, points=args.points, samples_per_point=args.samples)
            return
        if args.probe:
            quick_probe(ser)
            return
        if args.distance:
            distance_loop(ser, args.period)
            return
        interactive(ser)
    finally:
        ser.close()

DIST_RE = re.compile(r"distance:\s*([-+]?\d*\.?\d+)")

def parse_distance(resp: str) -> float | None:
    """
    Extracts distance float from a BU03 AT+DISTANCE response.
    Returns None if not found.
    """
    m = DIST_RE.search(resp)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None

def linfit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """
    Ordinary least squares fit for y = a*x + b
    Returns (a, b).
    """
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("Need at least 2 paired samples for linear fit")

    n = len(xs)
    xbar = sum(xs) / n
    ybar = sum(ys) / n

    sxx = sum((x - xbar) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("All measured values are identical; can't fit slope")

    sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    a = sxy / sxx
    b = ybar - a * xbar
    return a, b

def take_measurement(ser: serial.Serial, samples: int, settle_s: float = 0.05) -> float | None:
    """
    Takes multiple AT+DISTANCE samples, filters out 0.000000 and parse failures.
    Returns (mean_measured, good_count, total_count).
    Raises if no good samples.
    """
    vals: list[float] = []
    while len(vals) < samples:
        resp = send_cmd(ser, "AT+DISTANCE", settle_s=settle_s, max_wait_s=1.2)
        d = parse_distance(resp)
        print(f"Measurement: {d}")
        if d is None:
            print(f"No valid distance samples out of {len(vals)}. Last value was {vals[-1]}")
            continue
        vals.append(d)

    yield from vals

def set_cfg(id_number: int, ser: serial.Serial):
    if id_number > 10:
        raise ValueError(f"ID number must be between 0 and 10, got {id_number}. Will silently fail if not 0-10.")

    # From what I can tell, the group parameter doesn't actually do anything.  But setting it often helps with pairing it seems
    GROUP=100
    print(send_cmd(ser, "AT+GETDEV", max_wait_s=2.0))
    print(send_cmd(ser, "AT+GETCFG", max_wait_s=2.0))
    print(send_cmd(ser, f"AT+SETCFG={id_number},1,1,1，{GROUP}", max_wait_s=2.0))
    print(send_cmd(ser, "AT+SAVE", max_wait_s=2.0))
    print(send_cmd(ser, "AT+RESTART", max_wait_s=2.0))
    print(send_cmd(ser, "AT+GETCFG", max_wait_s=2.0))
    print()

def calibrate_mode(
    id_number: int,
    ser: serial.Serial,
    points: int,
    samples_per_point: int,
    setdev_prefix: str = "AT+SETDEV=5,16336,1,0.018,0.642",
):
    """
    Interactive calibration:
    - Prompts for true distance for each point
    - Measures distance via AT+DISTANCE averaging samples_per_point
    - Fits true = slope*measured + intercept
    - Programs slope/intercept into SETDEV and saves
    """
    print("\nCalibration mode")
    print("You will enter a known TRUE distance each step (use consistent units).")
    print("For best results: 5–10 points spanning your working range, 20–50 samples/point.")
    print("If you see lots of 0.000000, fix ranging first (channel/role, LOS, distance ~0.5–3m).\n")

    measured: list[float] = []
    truth: list[float] = []

    # Optional: show current dev params
    print("Current device params:")
    print(send_cmd(ser, "AT+RESTORE", max_wait_s=2.0))
    set_cfg(id_number, ser)
    print()

    for i in range(points):
        while True:
            s = input(f"[{i+1}/{points}] Enter TRUE distance (e.g. 1.25): ").strip()
            try:
                true_d = float(s)
                if true_d <= 0:
                    print("Must be > 0.")
                    continue
                break
            except ValueError:
                print("Not a number. Try again.")

        input("Place devices at that distance, then press Enter to measure...")

        try:
            for m in take_measurement(ser, samples=samples_per_point):
                measured.append(m)
                truth.append(true_d)
        except Exception as e:
            print(f"Measurement failed: {e}")
            print("Try again for this point.\n")
            i -= 1
            continue

    # Fit: TRUE = a * MEASURED + b
    a, b = linfit(measured, truth)

    # Report fit quality (simple R^2)
    yhat = [a*x + b for x in measured]
    ybar = sum(truth)/len(truth)
    ss_res = sum((y - yh)**2 for y, yh in zip(truth, yhat))
    ss_tot = sum((y - ybar)**2 for y in truth)
    r2 = 1.0 - (ss_res / ss_tot if ss_tot > 0 else float("nan"))

    print("Fit complete:")
    print(f"  slope (a):      {a:.8f}")
    print(f"  intercept (b):  {b:.8f}")
    print(f"  R^2:            {r2:.6f}")
    print("\nProgramming calibration into device...\n")

    setdev_cmd = f"{setdev_prefix},{a:.8f},{b:.8f},0,0"
    print("Sending:", setdev_cmd)
    print(send_cmd(ser, setdev_cmd, max_wait_s=2.0))
    print(send_cmd(ser, "AT+SAVE", max_wait_s=2.0))

    # Confirm
    print("\nUpdated device params:")
    print(send_cmd(ser, "AT+GETDEV", max_wait_s=2.0))
    print("\nDone.\n")

if __name__ == "__main__":
    main()
