"""Automatischer Test für Projekt 02 mit simulierten Pins (läuft ohne Hardware).

Aufruf: python3 test_materialstation.py
"""
import sys                                     # Suchpfad und Exit-Code
import threading                               # Taster-Drücke parallel zum Polling simulieren
import time                                    # Wartezeiten im Test
from pathlib import Path                       # Pfade

HIER = Path(__file__).resolve().parent         # Ordner dieses Tests
sys.path.insert(0, str(HIER))                  # die Programme dieses Projekts importierbar machen
sys.path.insert(0, str(HIER.parent / "gemeinsam"))  # und den gemeinsamen Ordner

from gpiozero import Device                    # noqa: E402  globale Einstellung der Pin-Fabrik
from gpiozero.pins.mock import MockFactory     # noqa: E402  simulierte Pins statt echter Hardware

Device.pin_factory = MockFactory()             # ab jetzt sind alle Pins simuliert

import materialstation_event as event          # noqa: E402  Variante 2
import materialstation_polling as polling      # noqa: E402  Variante 1
import pinplan                                 # noqa: E402  Pinnummern

fehler = 0                                     # Zähler für fehlgeschlagene Prüfungen


def pruefe(name, ok):                          # gibt OK/FEHLER aus und zählt Fehler
    global fehler                              # globalen Zähler verändern
    print(("OK     " if ok else "FEHLER ") + name)  # Ergebniszeile
    fehler += 0 if ok else 1                   # bei Fehler hochzählen


def druecken(pin, anzahl, abstand=0.12, start=0.0):  # simuliert mehrere saubere Tastendrücke
    time.sleep(start)                          # erst warten, bis das Programm seinen Taster angelegt hat
    for _ in range(anzahl):                    # so oft wie gewünscht
        pin.drive_low()                        # gedrückt: Taster zieht auf GND
        time.sleep(0.06)                       # kurz gedrückt halten
        pin.drive_high()                       # losgelassen: Pull-up zieht wieder hoch
        time.sleep(abstand)                    # Pause bis zum nächsten Druck


# ---------- Variante 1: Polling ----------
pin = Device.pin_factory.pin(pinplan.TASTER)   # simulierten Taster-Pin holen
pin.drive_high()                               # Ruhezustand HIGH (Pull-up)
helfer = threading.Thread(target=druecken, args=(pin, 3, 0.12, 0.2))  # drei Drücke im Hintergrund, Start nach 0,2 s
helfer.start()                                 # Drücke starten
ergebnis = polling.main(dauer_s=1.2)           # Polling 1,2 s laufen lassen
helfer.join()                                  # warten, bis der Helfer fertig ist
pruefe("Polling zählt drei Drücke", ergebnis == 3)  # genau drei erwartet
Device.pin_factory.reset()                     # alle simulierten Pins zurücksetzen

# ---------- Variante 1: Prellen ----------
pin = Device.pin_factory.pin(pinplan.TASTER)   # neuer simulierter Pin
pin.drive_high()                               # Ruhezustand
def prellen():                                 # ein Druck mit drei schnellen Störimpulsen
    time.sleep(0.2)                            # warten, bis das Programm bereit ist
    for _ in range(3):                         # dreimal innerhalb von 30 ms
        pin.drive_low()                        # kurz LOW
        time.sleep(0.005)                      # 5 ms
        pin.drive_high()                       # wieder HIGH
        time.sleep(0.005)                      # 5 ms
    pin.drive_low()                            # dann wirklich gedrückt
    time.sleep(0.1)                            # gehalten
    pin.drive_high()                           # losgelassen
helfer = threading.Thread(target=prellen)      # im Hintergrund ausführen
helfer.start()                                 # starten
ergebnis = polling.main(dauer_s=0.6)           # Polling laufen lassen
helfer.join()                                  # warten
pruefe("Polling zählt einen prellenden Druck höchstens zweimal", 1 <= ergebnis <= 2)  # 10-ms-Raster kann einen Impuls verpassen
Device.pin_factory.reset()                     # zurücksetzen

# ---------- Variante 2: Event ----------
event.zaehler = 0                              # Zähler auf 0
pin = Device.pin_factory.pin(pinplan.TASTER)   # simulierter Taster
pin.drive_high()                               # Ruhezustand
from gpiozero import LED, Button               # noqa: E402  Geräte für den Event-Test direkt anlegen
event.taster = Button(pinplan.TASTER, pull_up=True, bounce_time=event.ENTPRELL_S)  # wie in main()
event.led = LED(pinplan.LED_GRUEN)             # wie in main()
event.taster.when_pressed = event.angefordert  # Callback verbinden wie in main()
druecken(pin, 4, abstand=0.02)                 # vier saubere Drücke, der letzte endet kurz vor der Prüfung
pruefe("LED leuchtet direkt nach einem Druck", event.led.is_lit)  # Bestätigung ist sichtbar
time.sleep(0.6)                                # länger als LED_S warten
pruefe("Event zählt vier Drücke", event.zaehler == 4)  # genau vier erwartet
pruefe("LED ist nach 0,5 s wieder aus", not event.led.is_lit)  # Bestätigung endet von selbst
event.taster.close()                           # aufräumen
event.led.close()                              # aufräumen

print()                                        # Leerzeile vor dem Fazit
print("Alle Tests bestanden." if fehler == 0 else f"{fehler} Test(s) fehlgeschlagen.")  # Fazit
sys.exit(1 if fehler else 0)                   # Exit-Code für Skripte: 0 = alles gut
