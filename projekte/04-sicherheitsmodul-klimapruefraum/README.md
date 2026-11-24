<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 04 Climate test room safety module

If nobody moves in the test room for 15 seconds, a person might be unconscious. Then exactly one alarm is published via MQTT to `sentinel/lab01/safety/chamber01/alarm`. The last 9 seconds run as a countdown with the yellow LED blinking. Any movement cancels immediately.

## Wiring

| Part | GPIO (BCM) | Physical pin |
|---|:-:|:-:|
| PIR-Ausgang (optional) | GPIO17 | 11 |
| oder Taster als Ersatz | GPIO27 | 13 |
| LED gelb / yellow | GPIO8 | 24 |
| LED rot / red | GPIO25 | 22 |

All pins come from the [central pinout](../README.md#central-pinout).

## Run

```bash
cd projekte/04-sicherheitsmodul-klimapruefraum
python3 klimapruefraum.py           # mit PIR
python3 klimapruefraum.py --taster  # ohne PIR: Taster = Bewegung
```

## How it works

- The state logic lives in the class `Raumwaechter` and knows neither GPIO nor network. That makes it testable with artificial time, without waiting 15 seconds.
- All times use `time.monotonic()`, which does not jump when the Pi corrects its clock via NTP.
- A flag `alarm_gesendet` ensures exactly one alarm per incident. Only new movement resets it (re-arming).
- If the sensor reports movement for more than 120 s without a break, that counts as a sensor fault: no countdown, no alarm, red LED.
- Without a broker the local monitoring keeps running. The message honestly says "NICHT zugestellt" (not delivered).

## Tests

Automatic on the Pi: `test_klimapruefraum.py`: 10 checks for the required tests SM-01 to SM-07 and SM-11. All passing.

With real hardware (still open):

| Test | Expected | Result |
|---|---|:-:|
| 15 s nichts tun | Countdown 9 bis 0, dann genau ein Alarm | ⬜ |
| bei Countdown 5 Taster drücken | sofortiger Abbruch, kein Alarm | ⬜ |
| nach dem Alarm weiter warten | kein zweiter Alarm | ⬜ |
| Taster drücken, wieder 15 s warten | zweiter Alarm mit neuer `message_id` | ⬜ |

## Files

| File | Purpose |
|---|---|
| [`klimapruefraum.py`](klimapruefraum.py) | Zustandslogik, Hardware und MQTT-Alarm |
| [`test_klimapruefraum.py`](test_klimapruefraum.py) | Test der Zustandslogik mit künstlicher Zeit |

Every line of code has a German comment explaining what it does and why it is there.

## Limits

Learning demonstrator, not a certified safety system. The 7-segment display from the worksheet is replaced by terminal output and the yellow LED. The 15 s are a test value: the real PIR's hold time must be measured and the threshold must be at least 2 s above it.
