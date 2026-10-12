#!/usr/bin/env python3
"""Drive the bench over USB serial and write a JSON report.

Exit status:
    0  the run completed, every test passed, and at least --min-tests reported
    1  anything else, including a dead port or a firmware that never finished

The report is written on every path, including port errors, so the artifact is
never lost exactly when the bench misbehaved.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone

import serial

EXPECTED_FIRST_LINE = "BENCH-VALIDATOR RUN"
EXPECTED_LAST_LINE = "BENCH-VALIDATOR DONE"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse(line):
    parts = line.strip().split()
    if len(parts) < 3 or parts[0] != "TEST":
        return None
    rec = {"test": parts[1], "result": parts[2], "timestamp": now()}
    for p in parts[3:]:
        if "=" in p:
            k, v = p.split("=", 1)
            rec[k] = v
    return rec


def collect(ser, timeout):
    """Read until DONE, timeout, or a port error. Returns (results, started,
    done, port_error)."""
    results, started, done = [], False, False
    port_error = None
    t0 = time.time()
    while time.time() - t0 < timeout and not done:
        try:
            line = ser.readline().decode(errors="ignore")
        except (serial.SerialException, OSError) as exc:
            port_error = str(exc)
            break
        if EXPECTED_FIRST_LINE in line:
            started = True
        if EXPECTED_LAST_LINE in line:
            done = True
        rec = parse(line)
        if rec:
            results.append(rec)
    return results, started, done, port_error


def summarise(results, started, done, port_error, min_tests):
    passed = sum(1 for r in results if r["result"] == "PASS")
    failed = sum(1 for r in results if r["result"] == "FAIL")
    other = len(results) - passed - failed
    ok = (failed == 0 and other == 0 and done and len(results) >= min_tests
          and port_error is None)
    return {
        "started": started,
        "completed": done,
        "tests": results,
        "summary": {"total": len(results), "passed": passed, "failed": failed},
        "port_error": port_error,
        "ok": ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--out", default="report.json")
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--min-tests", type=int, default=5,
                    help="fail if fewer than this many tests reported")
    args = ap.parse_args()

    try:
        ser = serial.Serial(args.port, 115200, timeout=2)
    except (serial.SerialException, OSError) as exc:
        ser = None
        open_error = str(exc)
    else:
        open_error = None

    if ser is None:
        results, started, done = [], False, False
        port_error = f"cannot open {args.port}: {open_error}"
    else:
        with ser:
            ser.reset_input_buffer()
            results, started, done, port_error = collect(ser, args.timeout)

    report = summarise(results, started, done, port_error, args.min_tests)

    with open(args.out, "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report["summary"], indent=2))
    if port_error:
        print(f"port error: {port_error}", file=sys.stderr)
    if not done:
        print("firmware never reported completion", file=sys.stderr)
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
