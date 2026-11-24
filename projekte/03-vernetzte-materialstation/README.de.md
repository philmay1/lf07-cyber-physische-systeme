<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 03 Vernetzte Materialstation

Jeder Tastendruck wird eine Materialanforderung nach dem Topic-/Payload-Katalog von Tag 3 und geht per MQTT an `sentinel/lab01/material/station01/request`. Eine Leitstelle auf dem Pi oder einem zweiten Rechner empfängt, prüft und zählt die Nachrichten.

## Aufbau

| Bauteil | GPIO (BCM) | Physischer Pin |
|---|:-:|:-:|
| Taster / push button | GPIO27 | 13 |
| LED grün / green | GPIO7 | 26 |
| LED rot / red | GPIO25 | 22 |

Alle Pins kommen aus dem [zentralen Pinplan](../README.de.md#zentraler-pinplan).

## Starten

```bash
cd projekte/03-vernetzte-materialstation
python3 leitstelle.py          # Fenster 1: Empfänger
python3 materialstation_mqtt.py  # Fenster 2: Station
```

## So funktioniert es

- Der Taster-Callback legt nur einen Zeitpunkt in eine Warteschlange. Ein eigener Sende-Thread baut daraus die Nachricht, prüft sie gegen den Vertrag und sendet sie mit QoS 1, nicht retained. So blockiert ein langsames Netz nie den Taster.
- Jede Nachricht hat die sechs Pflichtfelder `device_id`, `event_type`, `timestamp` (UTC mit Z), `status`, `message_id` (UUID) und `schema_version`, dazu `request_count`. Eine Nachricht, die den Vertrag verletzt, wird nie gesendet.
- Vor dem Verbinden wird ein Last Will gesetzt: `offline` retained auf dem Status-Topic. Nach dem Verbinden kommt `online` retained. Verschwindet die Station ohne Abmeldung, meldet der Broker selbst `offline`.
- Die Leitstelle verwirft ungültige Nachrichten mit Grund und erkennt Duplikate an der `message_id`, weil QoS 1 eine Nachricht auch zweimal liefern kann.
- LED: grün Doppelblitz = verbunden, grün an = wird gesendet, zwei Blitze = Broker hat quittiert, rot langsam blinkend = keine Verbindung.

## Tests

Automatisch auf dem Pi: `test_vernetzt.py`: 17 Prüfungen, davon 10 Vertragsregeln, 4 zur Leitstelle und ein Durchlauf über den echten Mosquitto: 3 Anforderungen quittiert, online und offline empfangen. Alle grün.

Mit echten Bauteilen (noch offen):

| Test | Erwartet | Ergebnis |
|---|---|:-:|
| Leitstelle starten, dann Station | Leitstelle zeigt `online` (retained) | ⬜ |
| Taster 3-mal drücken | 3 gültige Anforderungen mit verschiedenen `message_id` | ⬜ |
| Broker stoppen (`sudo systemctl stop mosquitto`), Taster drücken | rot blinkt, Meldung "nicht zugestellt" | ⬜ |
| Station mit Strg+C beenden | Leitstelle zeigt `offline` | ⬜ |

## Dateien

| Datei | Aufgabe |
|---|---|
| [`materialstation_mqtt.py`](materialstation_mqtt.py) | Station: Taster, Warteschlange, Sende-Thread, LEDs |
| [`leitstelle.py`](leitstelle.py) | Subscriber: prüft, zählt, erkennt Duplikate |
| [`test_vernetzt.py`](test_vernetzt.py) | Vertragstests und Durchlauf über den Broker |

Jede Code-Zeile hat einen deutschen Kommentar, der erklärt, was sie tut und warum sie da ist.

## Grenzen

Der Broker läuft ohne Benutzer, Passwort und TLS. Fürs Schulnetz reicht das, im Betrieb nicht. Eine Quittung des Brokers (PUBACK) heißt nur, dass er die Nachricht hat, nicht, dass die Leitstelle sie verarbeitet hat.
