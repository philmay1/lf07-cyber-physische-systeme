# <Nr> <Projektname>

<!-- Vorlage: in den Projektordner kopieren, als README.de.md speichern (englische Fassung: PROJECT_README.md als README.md) und die Platzhalter in spitzen Klammern ersetzen. -->

<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

<img src="../../docs/badges/status-de.svg" alt="Status: in Arbeit">

<Ein bis zwei Sätze: Was macht das System, und welches Problem löst es? Beispiel: Ein Taster an der Materialstation meldet eine Entnahme, eine LED bestätigt sie.>

![Aufbau](../../docs/img/<projekt>-aufbau.jpg)

## Ziel

- <Was soll am Ende funktionieren?>
- <Woran erkenne ich, dass es funktioniert?>

## Hardware

| Bauteil | Anzahl | Hinweis |
|---|---|---|
| Raspberry Pi 400 | 1 | |
| <LED rot> | <1> | <mit 220-Ω-Vorwiderstand> |
| <Taster> | <1> | <interner Pull-up> |

## Pinbelegung

| Bauteil | GPIO (BCM) | Physischer Pin |
|---|---|---|
| <LED> | <GPIO17> | <11> |
| <Taster> | <GPIO27> | <13> |
| GND | | <6> |

Schaltplan: [schaltplan/<projekt>_schaltplan.png](schaltplan/<projekt>_schaltplan.png)

## Starten

```bash
cd projekte/<ordner>
python3 main.py
```

## So funktioniert es

<Den Ablauf in eigenen Worten erklären: Was liest das Programm ein, wie entscheidet es, was passiert danach? Ein Zustandsdiagramm oder Ablaufplan hilft.>

## Test

| Testfall | Erwartet | Ergebnis |
|---|---|---|
| <Taster drücken> | <LED leuchtet 2 s> | ⬜ |
| <Taster prellt> | <nur ein Ereignis> | ⬜ |

## Sicherheit

- <Elektrisch: Vorwiderstand, 3,3 V, Strom aus beim Umstecken>
- <Software: keine Passwörter im Code, Eingaben prüfen>

## Was ich gelernt habe

- <Wichtigste Erkenntnis>
- <Was ich beim nächsten Mal anders mache>
