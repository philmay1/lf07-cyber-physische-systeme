<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 03 Networked material station

Every button press becomes a material request according to the day 3 topic/payload catalog and is published via MQTT to `sentinel/lab01/material/station01/request`. A control-room subscriber on the Pi or a second computer receives, validates and counts the messages.

## Wiring

| Part | GPIO (BCM) | Physical pin |
|---|:-:|:-:|
| Taster / push button | GPIO27 | 13 |
| LED grün / green | GPIO7 | 26 |
| LED rot / red | GPIO25 | 22 |

All pins come from the [central pinout](../README.md#central-pinout).

## Run

```bash
cd projekte/03-vernetzte-materialstation
python3 leitstelle.py          # Fenster 1: Empfänger
python3 materialstation_mqtt.py  # Fenster 2: Station
```

## How it works

- The button callback only puts a timestamp into a queue. A separate sender thread builds the message, validates it against the contract and publishes it with QoS 1, not retained. A slow network never blocks the button.
- Each message has the six required fields `device_id`, `event_type`, `timestamp` (UTC with Z), `status`, `message_id` (UUID) and `schema_version`, plus `request_count`. A message that breaks the contract is never sent.
- A last will is set before connecting: `offline` retained on the status topic. After connecting, `online` is published retained. If the station disappears without disconnecting, the broker publishes `offline` itself.
- The control room rejects invalid messages with a reason and detects duplicates by `message_id`, because QoS 1 may deliver a message twice.
- LED: green double flash = connected, green on = sending, two flashes = broker acknowledged, red slow blink = no connection.

## Tests

Automatic on the Pi: `test_vernetzt.py`: 17 checks, 10 contract rules, 4 for the control room and a run over the real Mosquitto: 3 requests acknowledged, online and offline received. All passing.

With real hardware (still open):

| Test | Expected | Result |
|---|---|:-:|
| Leitstelle starten, dann Station | Leitstelle zeigt `online` (retained) | ⬜ |
| Taster 3-mal drücken | 3 gültige Anforderungen mit verschiedenen `message_id` | ⬜ |
| Broker stoppen (`sudo systemctl stop mosquitto`), Taster drücken | rot blinkt, Meldung "nicht zugestellt" | ⬜ |
| Station mit Strg+C beenden | Leitstelle zeigt `offline` | ⬜ |

## Files

| File | Purpose |
|---|---|
| [`materialstation_mqtt.py`](materialstation_mqtt.py) | Station: Taster, Warteschlange, Sende-Thread, LEDs |
| [`leitstelle.py`](leitstelle.py) | Subscriber: prüft, zählt, erkennt Duplikate |
| [`test_vernetzt.py`](test_vernetzt.py) | Vertragstests und Durchlauf über den Broker |

Every line of code has a German comment explaining what it does and why it is there.

## Limits

The broker runs without user, password and TLS. Fine for the school network, not for production. A broker acknowledgement (PUBACK) only means the broker has the message, not that the control room processed it.
