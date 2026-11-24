"""SENTINEL Projekt 02, Variante 2: Materialstation mit Event-Callback (Tag 2, AB3).

Hier fragt nicht das Programm den Taster ab, sondern gpiozero meldet sich bei jedem
Druck selbst und ruft eine Funktion auf ("Callback"). Das Hauptprogramm schläft so
lange mit pause() und braucht kaum Rechenzeit. Beenden mit Strg+C.

Schaltung (zentraler Pinplan): Taster GPIO27 (Pin 13) gegen GND, grüne LED GPIO7 (Pin 26) über 220 Ohm.
"""
import sys                                  # Suchpfad erweitern, damit der gemeinsame Ordner gefunden wird
import threading                            # Lock, damit der Zähler auch bei schnellen Drücken stimmt
from pathlib import Path                    # Pfade betriebssystemunabhängig zusammensetzen
from signal import pause                    # Hauptprogramm schlafen lassen, bis ein Signal kommt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gemeinsam"))  # projekte/gemeinsam importierbar machen

from gpiozero import LED, Button            # noqa: E402  Taster und LED aus gpiozero

import pinplan                              # noqa: E402  zentrale Pinbelegung

ENTPRELL_S = 0.05                           # gpiozero ignoriert 50 ms lang weitere Flanken
LED_S = 0.5                                 # Dauer der Bestätigung

taster = None                               # wird in main() angelegt; global, damit der Test ihn erreicht
led = None                                  # ebenso die LED
zaehler = 0                                 # Anzahl der Anforderungen
sperre = threading.Lock()                   # schützt den Zähler, falls Callbacks dicht hintereinander kommen


def angefordert():                          # der Callback: gpiozero ruft ihn bei jedem Druck auf
    global zaehler                          # den Zähler außerhalb der Funktion verändern
    with sperre:                            # nur ein Callback gleichzeitig darf zählen
        zaehler += 1                        # neue Anforderung
        nummer = zaehler                    # Wert für die Ausgabe sichern
    print(f"Materialanforderung {nummer}")  # Ereignis im Terminal
    led.blink(on_time=LED_S, off_time=0, n=1, background=True)  # LED 0,5 s an, ohne den Callback zu blockieren


def main():                                 # Hauptprogramm
    global taster, led                      # die globalen Variablen belegen
    taster = Button(pinplan.TASTER, pull_up=True, bounce_time=ENTPRELL_S)  # Pull-up und Entprellung in einem
    led = LED(pinplan.LED_GRUEN)            # grüne LED
    taster.when_pressed = angefordert       # Funktion verbinden, ohne Klammern: gpiozero ruft sie später auf
    print("Materialstation (Event) bereit. Taster drücken, Strg+C beendet.")  # Startmeldung
    try:                                    # geschützter Block
        pause()                             # schlafen, bis Strg+C kommt; die Arbeit machen die Callbacks
    except KeyboardInterrupt:               # Strg+C
        print(f"\nBeendet. {zaehler} Anforderungen gezählt.")  # Abschluss
    finally:                                # Aufräumen in jedem Fall
        taster.when_pressed = None          # Callback lösen, damit beim Beenden nichts mehr ausgelöst wird
        led.off()                           # LED aus
        led.close()                         # GPIO7 freigeben
        taster.close()                      # GPIO27 freigeben


if __name__ == "__main__":                  # nur beim direkten Start
    main()                                  # los geht's
