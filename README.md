# avionics-test-bench
RP2040 hardware self-test harness. Exercises GPIO, I2C, SPI, ADC, UART.
Host script writes a JSON report and exits nonzero if the bench did not pass.

## Covers
Hardware Test Engineer · Board-Level Test Engineer · Test Technician · QA Engineer · Hardware Validation Engineer (entry-level)

## Wiring
Two jumpers are required, or the tests fail on purpose:

| Jumper | Pins            | Tested by        |
|--------|-----------------|------------------|
| 1      | GP6 ↔ GP7       | `gpio_loopback`  |
| 2      | GP16 ↔ GP19     | `spi_loopback`   |

`i2c_scan` needs no wiring: with nothing attached it passes with `value=0`,
and fails only if the bus is stuck or shorted. `adc_read` checks that a
conversion completes and the code is in range — GP26 is floating, so no
voltage is asserted.

## Build
```bash
export PICO_SDK_PATH=/path/to/pico-sdk
cmake -G Ninja -S firmware -B build -DPICO_BOARD=pico -DCMAKE_BUILD_TYPE=Release
cmake --build build          # -> build/bench_validator.uf2
```

## Quickstart
```bash
# copy build/bench_validator.uf2 onto the Pico (BOOTSEL drag-and-drop)
pip install -r host/requirements.txt
python host/validate.py --port /dev/ttyACM0
```

`validate.py` exits 0 only if the run completed, every test passed, and at
least `--min-tests` (default 5) tests reported. A dead port still produces a
report with `port_error` set rather than a traceback.

## Output
See `docs/output.json`:
```json
{"total": 5, "passed": 5, "failed": 0}
```

## Tests
```bash
pip install pytest
python -m pytest host/test_validate.py -q
```
The suite drives the real script over a pty, so no hardware is needed: healthy
run, a failing test, an unexpected result string, a dead port, a missing DONE
line, and a short run caught by `--min-tests`.

## What works
GPIO loopback in both directions, I2C scan with bus-fault detection, SPI
loopback, ADC conversion check, UART init, JSON report with a meaningful exit
code, pty-based test suite, CI that builds the firmware.

## What doesn't
No power-rail monitoring yet. No fault injection yet. No JUnit output yet.
Nothing has been exercised on real silicon — the firmware is CI-built, not
bench-run.

## License
MIT
