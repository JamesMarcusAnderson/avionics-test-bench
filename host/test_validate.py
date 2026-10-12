"""Tests for host/validate.py, driving the real script over a pty."""
import json
import os
import pathlib
import pty
import subprocess
import sys
import tempfile
import time

import pytest

REPO = pathlib.Path(__file__).parent.parent
VALIDATE = REPO / "host" / "validate.py"

FW_OUTPUT = (
    "BENCH-VALIDATOR RUN\r\n"
    "TEST gpio_loopback PASS\r\n"
    "TEST i2c_scan PASS value=0\r\n"
    "TEST spi_loopback PASS value=2\r\n"
    "TEST adc_read PASS value=512\r\n"
    "TEST uart_init PASS\r\n"
    "BENCH-VALIDATOR DONE\r\n"
)


def run_validate(payload, extra=(), close_master=True, wait=12):
    """Spawn validate.py against a pty, optionally feed it bytes, return
    (exit_code, stdout, stderr, report_dict_or_None)."""
    master, slave = pty.openpty()
    port = os.ttyname(slave)
    out = pathlib.Path(tempfile.mkdtemp()) / "report.json"
    proc = subprocess.Popen(
        [sys.executable, str(VALIDATE), "--port", port, "--out", str(out),
         "--timeout", "6", *extra],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.0)
    if payload:
        os.write(master, payload.encode())
        time.sleep(1.0)
    if close_master:
        os.close(master)
    try:
        stdout, stderr = proc.communicate(timeout=wait)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
        pytest.fail(f"validate.py hung\nstdout={stdout}\nstderr={stderr}")
    report = json.loads(out.read_text()) if out.exists() else None
    return proc.returncode, stdout, stderr, report


def test_healthy_run_passes():
    code, stdout, stderr, report = run_validate(FW_OUTPUT)
    assert code == 0, stderr
    assert report["summary"] == {"total": 5, "passed": 5, "failed": 0}
    assert report["started"] is True
    assert report["completed"] is True
    assert report["ok"] is True
    assert report["port_error"] is None


def test_report_keys_match_documented_sample():
    """docs/output.json is the published contract for the report shape."""
    _, _, _, report = run_validate(FW_OUTPUT)
    committed = json.loads((REPO / "docs" / "output.json").read_text())
    assert set(committed).issubset(report)
    assert [t["test"] for t in report["tests"]] == [t["test"] for t in committed["tests"]]
    assert [t["result"] for t in report["tests"]] == [t["result"] for t in committed["tests"]]


def test_a_failing_test_fails_the_run():
    payload = FW_OUTPUT.replace("TEST spi_loopback PASS", "TEST spi_loopback FAIL")
    code, _, _, report = run_validate(payload)
    assert code == 1
    assert report["summary"] == {"total": 5, "passed": 4, "failed": 1}
    assert report["ok"] is False


def test_unexpected_result_string_fails_the_run():
    payload = FW_OUTPUT.replace("TEST adc_read PASS", "TEST adc_read ERROR")
    code, _, _, report = run_validate(payload)
    assert code == 1
    assert report["summary"]["failed"] == 0     # not PASS and not FAIL
    assert report["ok"] is False


def test_dead_port_writes_a_report_and_fails():
    """The regression: an unreadable port used to raise and write nothing."""
    code, _, stderr, report = run_validate("")
    assert code == 1
    assert report is not None, "report.json must be written even on a port error"
    assert report["port_error"]
    assert report["summary"]["total"] == 0
    assert "port error" in stderr


def test_missing_done_line_fails_the_run():
    payload = ("BENCH-VALIDATOR RUN\r\n"
               "TEST gpio_loopback PASS\r\n"
               "TEST i2c_scan PASS value=0\r\n")
    code, _, stderr, report = run_validate(payload)
    assert code == 1
    assert report["completed"] is False
    assert "never reported completion" in stderr


def test_min_tests_catches_a_short_run():
    """Firmware that prints DONE after only two tests must not pass."""
    payload = ("BENCH-VALIDATOR RUN\r\n"
               "TEST gpio_loopback PASS\r\n"
               "TEST i2c_scan PASS value=0\r\n"
               "BENCH-VALIDATOR DONE\r\n")
    code, _, _, report = run_validate(payload)
    assert code == 1
    assert report["completed"] is True
    assert report["summary"]["failed"] == 0
    assert report["ok"] is False


def test_min_tests_can_be_relaxed():
    payload = ("BENCH-VALIDATOR RUN\r\n"
               "TEST gpio_loopback PASS\r\n"
               "BENCH-VALIDATOR DONE\r\n")
    code, _, _, report = run_validate(payload, extra=["--min-tests", "1"])
    assert code == 0
    assert report["summary"]["total"] == 1


def test_unopenable_port_is_reported_not_traced():
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), "--port", "/dev/definitely-not-a-port",
         "--out", os.path.join(tempfile.mkdtemp(), "r.json"), "--timeout", "2"],
        capture_output=True, text=True)
    assert proc.returncode == 1
    assert "Traceback" not in proc.stderr
    assert "cannot open" in proc.stderr


def test_parse_ignores_non_test_lines():
    sys.path.insert(0, str(REPO / "host"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("validate", VALIDATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.parse("BENCH-VALIDATOR RUN") is None
    assert mod.parse("") is None
    assert mod.parse("random noise") is None
    assert mod.parse("TEST a PASS")["test"] == "a"
    rec = mod.parse("TEST i2c_scan PASS value=3 extra=1")
    assert rec["value"] == "3" and rec["extra"] == "1"
