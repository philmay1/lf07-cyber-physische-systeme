<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 02 Local material station

A push button reports a material request, the green LED confirms each press for 0.5 s. There are two variants to show the difference: polling checks the button every 10 ms, the event variant lets gpiozero call it on each press and sleeps in between.

## Wiring

| Part | GPIO (BCM) | Physical pin |
|---|:-:|:-:|
| Taster / push button | GPIO27 | 13 |
| LED grün / green | GPIO7 | 26 |

All pins come from the [central pinout](../README.md#central-pinout).

## Run

```bash
cd projekte/02-lokale-materialstation
python3 materialstation_polling.py
python3 materialstation_event.py
```

## How it works

- Polling: a loop reads `taster.is_pressed`, detects the change from released to pressed (edge) and ignores further edges for 50 ms to debounce. The LED is switched off by a deadline instead of `sleep`, so no press gets lost.
- Event: `Button(27, pull_up=True, bounce_time=0.05)` debounces by itself, `when_pressed` calls `angefordert()`. A lock protects the counter if two callbacks arrive close together. The main program waits in `pause()` and uses almost no CPU.

## Tests

Automatic on the Pi: `test_materialstation.py`: 5 checks (polling counts 3 presses, bouncing, event counts 4 presses, LED on and off again). All passing.

With real hardware (still open):

| Test | Expected | Result |
|---|---|:-:|
| Taster 5-mal drücken | 5 Anforderungen, LED blitzt jedes Mal | ⬜ |
| Taster schnell hintereinander | jeder Druck zählt genau einmal | ⬜ |
| Strg+C | Summe wird angezeigt, LED aus | ⬜ |

## Files

| File | Purpose |
|---|---|
| [`materialstation_polling.py`](materialstation_polling.py) | Variante 1: Polling |
| [`materialstation_event.py`](materialstation_event.py) | Variante 2: Event-Callback |
| [`test_materialstation.py`](test_materialstation.py) | automatischer Test mit simulierten Pins |

Every line of code has a German comment explaining what it does and why it is there.

## Limits

Requests are only counted and printed. Sending them is project 03.
