<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 05 Lokale Zutrittskontrolle

PIN am 4x4-Keypad tippen, `#` prüft. Richtig: grün, zwei Pieptöne, der Servo SG90 fährt von 0° auf 90°, hält 3 s und fährt zurück. Falsch: rot 1 s, der Servo bewegt sich nicht.

## Aufbau

| Bauteil | GPIO (BCM) | Physischer Pin |
|---|:-:|:-:|
| Keypad R1 bis R4 | GPIO5, 6, 13, 19 | 29, 31, 33, 35 |
| Keypad C1 bis C4 | GPIO12, 16, 20, 21 | 32, 36, 38, 40 |
| Servo Signal | GPIO18 | 12 |
| Servo +5 V / GND | 5 V / GND | 2 / 6 |
| LEDs rot, gelb, grün | GPIO25, 8, 7 | 22, 24, 26 |
| Summer / buzzer | GPIO22 | 15 |

Alle Pins kommen aus dem [zentralen Pinplan](../README.de.md#zentraler-pinplan).

## Starten

```bash
cd projekte/05-lokale-zutrittskontrolle
cp config.example.ini config.ini   # einmalig, Test-PIN eintragen
python3 zutritt_lokal.py
python3 zutritt_lokal.py --mqtt     # meldet granted/denied
```

## So funktioniert es

- Das Keypad wird alle 20 ms gescannt: Zeile für Zeile auf HIGH, Spalten abfragen. Mehrere gleichzeitig gedrückte Tasten werden abgelehnt.
- Die PIN-Eingabe ist ein Zustandsautomat: höchstens 4 Ziffern, `*` löscht die letzte, `#` prüft nur bei genau 4 Stellen, nach 10 s ohne Taste wird alles gelöscht.
- Der Servo startet in der verriegelten Position und bekommt danach kein Signal mehr (`detach`). Mit laufendem `pigpiod` kommen die Pulse hardwaregenau, sonst per Software-PWM.
- Die Prüfung ist eine austauschbare Funktion `verify_pin(pin)`. Hier vergleicht sie mit der Test-PIN aus `config.ini`, in Projekt 06 mit MariaDB und Argon2. Scanner und Servo bleiben dabei gleich.
- Die PIN erscheint nie im Terminal, im Log oder in MQTT. Gesendet wird nur `granted`, `denied` oder `technical_error`.

## Tests

Automatisch auf dem Pi: `test_zutritt_lokal.py`: 15 Prüfungen zu ZT-01 bis ZT-05 und ZT-07, Keypad-Scan und Servo-Sequenz mit simulierten Pins. Alle grün.

Mit echten Bauteilen (noch offen):

| Test | Erwartet | Ergebnis |
|---|---|:-:|
| richtige PIN + `#` | grün, 2 Pieptöne, Servo 0° → 90° → 3 s → 0° | ⬜ |
| falsche PIN + `#` | rot 1 s, kein Servo | ⬜ |
| 3 Ziffern + `#` | zweimal rot blinken, keine Prüfung | ⬜ |
| 5 Ziffern | fünfte wird ignoriert | ⬜ |
| 2 Ziffern, 10 s warten | Eingabe gelöscht | ⬜ |
| Strg+C | Servo verriegelt, alles aus | ⬜ |

## Dateien

| Datei | Aufgabe |
|---|---|
| [`zutritt_lokal.py`](zutritt_lokal.py) | Programm mit lokaler PIN-Prüfung |
| [`config.example.ini`](config.example.ini) | Vorlage, `config.ini` selbst ist per `.gitignore` ausgeschlossen |
| [`test_zutritt_lokal.py`](test_zutritt_lokal.py) | automatischer Test |

Jede Code-Zeile hat einen deutschen Kommentar, der erklärt, was sie tut und warum sie da ist.

## Grenzen

Die Klartext-PIN in `config.ini` ist laut Arbeitsblatt eine bewusst unsichere Lernstufe. Projekt 06 ersetzt sie. Der Servo aus dem Pi versorgt reicht nur für kurze Tests ohne Last.
