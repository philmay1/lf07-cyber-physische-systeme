<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# SENTINEL-Projekte

Die zehn Projekte aus der Agenda von Lernfeld 7. Ab Projekt 02 teilen sich alle Projekte einen Aufbau auf dem Steckbrett, einen zentralen Pinplan und gemeinsame Bausteine im Ordner [`gemeinsam/`](gemeinsam/).

| Nr. | Projekt | Stand |
|:-:|---|:-:|
| 01 | [SENTINEL Projektstart](01-sentinel-projektstart/) | ✅ am Pi getestet |
| 02 | [Lokale Materialstation](02-lokale-materialstation/) | 🟡 Code und Tests fertig, Aufbau am Pi offen |
| 03 | [Vernetzte Materialstation](03-vernetzte-materialstation/) | 🟡 Code und Tests fertig, Aufbau am Pi offen |
| 04 | [Sicherheitsmodul Klimaprüfraum](04-sicherheitsmodul-klimapruefraum/) | 🟡 Code und Tests fertig, Aufbau am Pi offen |
| 05 | [Lokale Zutrittskontrolle](05-lokale-zutrittskontrolle/) | 🟡 Code und Tests fertig, Aufbau am Pi offen |
| 06 | [Dynamische Zutrittskontrolle](06-dynamische-zutrittskontrolle/) | 🟡 Code fertig, MariaDB auf dem Pi getestet, Aufbau offen |
| 07 bis 10 | Umweltüberwachung, Transportbox, Release Readiness, Kundenabnahme | ⬜ Arbeitsblätter vorhanden, Code folgt mit der Hardware |

"Code und Tests fertig" heißt: Die automatischen Tests laufen auf dem Pi mit simulierten Pins grün. Mit echten Bauteilen ist das Projekt erst getestet, wenn die Testtabelle in seiner README abgehakt ist.

## Zentraler Pinplan

Grundlage ist das Anschlussbild des Dozenten für Pi 400, Keypad und Servo SG90. Die Ampel-LEDs aus Tag 3 bleiben gesteckt. Alle Programme lesen die Pins aus [`gemeinsam/pinplan.py`](gemeinsam/pinplan.py).

| Bauteil | GPIO (BCM) | Physischer Pin | Hinweis |
|---|:-:|:-:|---|
| LED rot | GPIO25 | 22 | über 220 Ω |
| LED gelb | GPIO8 | 24 | über 220 Ω |
| LED grün | GPIO7 | 26 | über 220 Ω |
| Taster | GPIO27 | 13 | gegen GND, interner Pull-up |
| Summer (PNP-Transistor) | GPIO22 | 15 | 1 kΩ an die Basis, Emitter an 3V3 (Pin 17) |
| Bewegungsmelder PIR (optional) | GPIO17 | 11 | Ausgang darf höchstens 3,3 V liefern |
| Keypad R1 bis R4 | GPIO5, 6, 13, 19 | 29, 31, 33, 35 | Zeilen, Ausgänge |
| Keypad C1 bis C4 | GPIO12, 16, 20, 21 | 32, 36, 38, 40 | Spalten, interner Pull-down |
| Servo SG90 Signal | GPIO18 | 12 | orange/gelb |
| Servo +5 V | 5 V | 2 | rot |
| Servo GND | GND | 6 | braun/schwarz |
| GND-Schiene | GND | 20 | für LEDs, Taster, Summer |

> [!WARNING]
> Nur stromlos umstecken. Der Servo bekommt 5 V, sein Signal kommt aber vom 3,3-V-GPIO. Laut Bild des Dozenten reicht die Versorgung aus dem Pi nur für kurze Tests ohne Last. Ruckelt der Servo oder startet der Pi neu, braucht er ein eigenes 5-V-Netzteil mit gemeinsamer Masse.

### Umbau gegenüber den Übungen von Tag 3 und Tag 5

| Was | vorher | jetzt | Warum |
|---|---|---|---|
| Summer | GPIO18 (Pin 12) | GPIO22 (Pin 15) | GPIO18 ist jetzt das Servo-Signal |
| Taster | GPIO12 (Pin 32) | GPIO27 (Pin 13) | GPIO12 ist jetzt Keypad C1 |
| Keypad C1 | GPIO26 (Pin 37) | GPIO12 (Pin 32) | so steht es im Bild des Dozenten |

Die Übungen in [`../uebungen/`](../uebungen/) behalten ihre alten Pins und laufen nur mit ihrem damaligen Aufbau.

## Gemeinsame Bausteine

| Datei | Aufgabe |
|---|---|
| [`pinplan.py`](gemeinsam/pinplan.py) | alle Pins an einer Stelle |
| [`vertrag.py`](gemeinsam/vertrag.py) | Topic-/Payload-Katalog 1.0.0 von Tag 3: Nachrichten bauen und prüfen |
| [`mqtt_verbindung.py`](gemeinsam/mqtt_verbindung.py) | MQTT mit Last Will, online/offline-Status und Warten auf die Quittung |
| [`keypad.py`](gemeinsam/keypad.py) | 4x4-Keypad scannen, Mehrfachtasten ablehnen |
| [`pin_eingabe.py`](gemeinsam/pin_eingabe.py) | PIN-Zustandsautomat: 4 Ziffern, `*`, `#`, Timeout |
| [`tuer.py`](gemeinsam/tuer.py) | Servo-Sequenz 0° → 90° → 3 s → 0° mit LED- und Summer-Rückmeldung |
| [`zutritt_ablauf.py`](gemeinsam/zutritt_ablauf.py) | gemeinsame Hauptschleife für Projekt 05 und 06 |

## Alle Tests auf einmal

```bash
bash projekte/alle_tests.sh
```

Der Durchlauf über den echten Broker (Projekt 03) und die echte Datenbank (Projekt 06) läuft nur, wenn Mosquitto und MariaDB auf dem Pi eingerichtet sind. Sonst meldet der Test das als HINWEIS und überspringt diesen Teil.
