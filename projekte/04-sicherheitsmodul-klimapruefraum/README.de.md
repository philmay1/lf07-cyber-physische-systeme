<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 04 Sicherheitsmodul Klimaprüfraum

Bewegt sich im Prüfraum 15 Sekunden lang niemand, könnte eine Person bewusstlos sein. Dann geht genau ein Alarm per MQTT an `sentinel/lab01/safety/chamber01/alarm`. Die letzten 9 Sekunden laufen als Countdown, die gelbe LED blinkt dazu. Jede Bewegung bricht sofort ab.

## Aufbau

| Bauteil | GPIO (BCM) | Physischer Pin |
|---|:-:|:-:|
| PIR-Ausgang (optional) | GPIO17 | 11 |
| oder Taster als Ersatz | GPIO27 | 13 |
| LED gelb / yellow | GPIO8 | 24 |
| LED rot / red | GPIO25 | 22 |

Alle Pins kommen aus dem [zentralen Pinplan](../README.de.md#zentraler-pinplan).

## Starten

```bash
cd projekte/04-sicherheitsmodul-klimapruefraum
python3 klimapruefraum.py           # mit PIR
python3 klimapruefraum.py --taster  # ohne PIR: Taster = Bewegung
```

## So funktioniert es

- Die Zustandslogik steckt in der Klasse `Raumwaechter` und kennt weder GPIO noch Netz. Deshalb lässt sie sich mit künstlicher Zeit testen, ohne 15 Sekunden zu warten.
- Alle Zeiten laufen über `time.monotonic()`. Diese Uhr springt nicht, wenn der Pi seine Uhrzeit per NTP korrigiert.
- Ein Flag `alarm_gesendet` sorgt für genau einen Alarm pro Vorfall. Erst eine neue Bewegung setzt es zurück (Wieder-Scharfschaltung).
- Meldet der Sensor länger als 120 s ununterbrochen Bewegung, gilt das als Sensorfehler. Dann gibt es weder Countdown noch Alarm, sondern rot.
- Fehlt der Broker, läuft die lokale Überwachung trotzdem weiter. Die Meldung sagt ehrlich "NICHT zugestellt".

## Tests

Automatisch auf dem Pi: `test_klimapruefraum.py`: 10 Prüfungen zu den Pflichtnachweisen SM-01 bis SM-07 und SM-11. Alle grün.

Mit echten Bauteilen (noch offen):

| Test | Erwartet | Ergebnis |
|---|---|:-:|
| 15 s nichts tun | Countdown 9 bis 0, dann genau ein Alarm | ⬜ |
| bei Countdown 5 Taster drücken | sofortiger Abbruch, kein Alarm | ⬜ |
| nach dem Alarm weiter warten | kein zweiter Alarm | ⬜ |
| Taster drücken, wieder 15 s warten | zweiter Alarm mit neuer `message_id` | ⬜ |

## Dateien

| Datei | Aufgabe |
|---|---|
| [`klimapruefraum.py`](klimapruefraum.py) | Zustandslogik, Hardware und MQTT-Alarm |
| [`test_klimapruefraum.py`](test_klimapruefraum.py) | Test der Zustandslogik mit künstlicher Zeit |

Jede Code-Zeile hat einen deutschen Kommentar, der erklärt, was sie tut und warum sie da ist.

## Grenzen

Lern-Demonstrator, kein zugelassenes Sicherheitssystem. Die 7-Segment-Anzeige aus dem Arbeitsblatt ist durch Terminal und gelbe LED ersetzt. Die 15 s sind ein Prüfwert: Am echten PIR muss die Nachlaufzeit gemessen werden, die Schwelle muss mindestens 2 s darüber liegen.
