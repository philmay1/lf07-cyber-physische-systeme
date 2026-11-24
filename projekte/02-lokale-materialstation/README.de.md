<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 02 Lokale Materialstation

Ein Taster meldet eine Materialanforderung, die grüne LED bestätigt jeden Druck 0,5 s lang. Das Projekt gibt es in zwei Varianten, damit man den Unterschied sieht: Polling fragt den Taster alle 10 ms selbst ab, die Event-Variante lässt sich von gpiozero bei jedem Druck aufrufen und schläft dazwischen.

## Aufbau

| Bauteil | GPIO (BCM) | Physischer Pin |
|---|:-:|:-:|
| Taster / push button | GPIO27 | 13 |
| LED grün / green | GPIO7 | 26 |

Alle Pins kommen aus dem [zentralen Pinplan](../README.de.md#zentraler-pinplan).

## Starten

```bash
cd projekte/02-lokale-materialstation
python3 materialstation_polling.py
python3 materialstation_event.py
```

## So funktioniert es

- Polling: Eine Schleife liest `taster.is_pressed`, erkennt den Wechsel von nicht gedrückt auf gedrückt (Flanke) und ignoriert 50 ms lang weitere Flanken gegen Prellen. Die LED wird nicht mit `sleep` gehalten, sondern über eine Ausschaltzeit, damit kein Druck verloren geht.
- Event: `Button(27, pull_up=True, bounce_time=0.05)` entprellt selbst, `when_pressed` ruft die Funktion `angefordert()` auf. Ein Lock schützt den Zähler, falls zwei Callbacks dicht hintereinander kommen. Das Hauptprogramm wartet mit `pause()` und braucht kaum Rechenzeit.

## Tests

Automatisch auf dem Pi: `test_materialstation.py`: 5 Prüfungen (Polling zählt 3 Drücke, Prellen, Event zählt 4 Drücke, LED an und wieder aus). Alle grün.

Mit echten Bauteilen (noch offen):

| Test | Erwartet | Ergebnis |
|---|---|:-:|
| Taster 5-mal drücken | 5 Anforderungen, LED blitzt jedes Mal | ⬜ |
| Taster schnell hintereinander | jeder Druck zählt genau einmal | ⬜ |
| Strg+C | Summe wird angezeigt, LED aus | ⬜ |

## Dateien

| Datei | Aufgabe |
|---|---|
| [`materialstation_polling.py`](materialstation_polling.py) | Variante 1: Polling |
| [`materialstation_event.py`](materialstation_event.py) | Variante 2: Event-Callback |
| [`test_materialstation.py`](test_materialstation.py) | automatischer Test mit simulierten Pins |

Jede Code-Zeile hat einen deutschen Kommentar, der erklärt, was sie tut und warum sie da ist.

## Grenzen

Die Anforderungen werden nur gezählt und im Terminal gezeigt. Gesendet wird erst in Projekt 03.
