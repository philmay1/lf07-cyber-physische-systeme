<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# SENTINEL projects

The ten projects from the learning field 7 agenda. From project 02 on, all projects share one breadboard setup, one central pinout and common building blocks in [`gemeinsam/`](gemeinsam/).

| No. | Project | State |
|:-:|---|:-:|
| 01 | [SENTINEL kickoff](01-sentinel-projektstart/) | ✅ tested on the Pi |
| 02 | [Local material station](02-lokale-materialstation/) | 🟡 code and tests done, hardware test pending |
| 03 | [Networked material station](03-vernetzte-materialstation/) | 🟡 code and tests done, hardware test pending |
| 04 | [Climate test room safety module](04-sicherheitsmodul-klimapruefraum/) | 🟡 code and tests done, hardware test pending |
| 05 | [Local access control](05-lokale-zutrittskontrolle/) | 🟡 code and tests done, hardware test pending |
| 06 | [Dynamic access control](06-dynamische-zutrittskontrolle/) | 🟡 code done, MariaDB tested on the Pi, hardware test pending |
| 07 to 10 | Environment, transport box, release readiness, acceptance | ⬜ worksheets done, code follows with the hardware |

"Code and tests done" means the automatic tests pass on the Pi with simulated pins. A project counts as tested on hardware once the test table in its README is ticked.

## Central pinout

Based on the instructor's wiring picture for Pi 400, keypad and SG90 servo. The traffic light LEDs from day 3 stay in place. All programs read their pins from [`gemeinsam/pinplan.py`](gemeinsam/pinplan.py).

| Part | GPIO (BCM) | Physical pin | Note |
|---|:-:|:-:|---|
| LED red | GPIO25 | 22 | via 220 Ω |
| LED yellow | GPIO8 | 24 | via 220 Ω |
| LED green | GPIO7 | 26 | via 220 Ω |
| Push button | GPIO27 | 13 | to GND, internal pull-up |
| Buzzer (PNP transistor) | GPIO22 | 15 | 1 kΩ to the base, emitter to 3V3 (pin 17) |
| PIR motion sensor (optional) | GPIO17 | 11 | output must not exceed 3.3 V |
| Keypad R1 to R4 | GPIO5, 6, 13, 19 | 29, 31, 33, 35 | rows, outputs |
| Keypad C1 to C4 | GPIO12, 16, 20, 21 | 32, 36, 38, 40 | columns, internal pull-down |
| Servo SG90 signal | GPIO18 | 12 | orange/yellow |
| Servo +5 V | 5 V | 2 | red |
| Servo GND | GND | 6 | brown/black |
| GND rail | GND | 20 | for LEDs, button, buzzer |

> [!WARNING]
> Rewire only with the power off. The servo gets 5 V, but its signal comes from a 3.3 V GPIO. Powering it from the Pi is only fine for short tests without load. If it jitters or the Pi reboots, use a separate 5 V supply with a common ground.

### Changes compared to the day 3 and day 5 exercises

| What | before | now | Why |
|---|---|---|---|
| Buzzer | GPIO18 (pin 12) | GPIO22 (pin 15) | GPIO18 is now the servo signal |
| Push button | GPIO12 (pin 32) | GPIO27 (pin 13) | GPIO12 is now keypad C1 |
| Keypad C1 | GPIO26 (pin 37) | GPIO12 (pin 32) | as in the instructor's picture |

The exercises in [`../uebungen/`](../uebungen/) keep their old pins and only run with their original wiring.

## Common building blocks

| File | Purpose |
|---|---|
| [`pinplan.py`](gemeinsam/pinplan.py) | all pins in one place |
| [`vertrag.py`](gemeinsam/vertrag.py) | topic/payload catalog 1.0.0 from day 3: build and validate messages |
| [`mqtt_verbindung.py`](gemeinsam/mqtt_verbindung.py) | MQTT with last will, online/offline status and waiting for the broker ack |
| [`keypad.py`](gemeinsam/keypad.py) | scan the 4x4 keypad, reject multiple keys |
| [`pin_eingabe.py`](gemeinsam/pin_eingabe.py) | PIN state machine: 4 digits, `*`, `#`, timeout |
| [`tuer.py`](gemeinsam/tuer.py) | servo sequence 0° → 90° → 3 s → 0° with LED and buzzer feedback |
| [`zutritt_ablauf.py`](gemeinsam/zutritt_ablauf.py) | shared main loop for projects 05 and 06 |

## Run all tests

```bash
bash projekte/alle_tests.sh
```

The run against the real broker (project 03) and the real database (project 06) only happens when Mosquitto and MariaDB are set up on the Pi. Otherwise the test prints a HINWEIS (note) and skips that part.
