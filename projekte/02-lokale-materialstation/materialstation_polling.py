"""SENTINEL Projekt 02, Variante 1: Materialstation mit Polling (Tag 2, AB3).

Das Programm fragt den Taster alle 10 ms selbst ab ("Polling"). Jeder neue Druck
zählt als eine Materialanforderung, die grüne LED leuchtet 0,5 s zur Bestätigung.
Beenden mit Strg+C.

Schaltung (zentraler Pinplan): Taster GPIO27 (Pin 13) gegen GND, grüne LED GPIO7 (Pin 26) über 220 Ohm.
"""
import sys                                  # Suchpfad erweitern, damit der gemeinsame Ordner gefunden wird
import time                                 # monotone Uhr und Pausen
from pathlib import Path                    # Pfade betriebssystemunabhängig zusammensetzen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gemeinsam"))  # projekte/gemeinsam importierbar machen

from gpiozero import LED, Button            # noqa: E402  Taster und LED aus gpiozero

import pinplan                              # noqa: E402  zentrale Pinbelegung

ABFRAGE_S = 0.01                            # alle 10 ms nachsehen: schnell genug für jeden Tastendruck
ENTPRELL_S = 0.05                           # 50 ms Sperrzeit nach einem Druck gegen Kontaktprellen
LED_S = 0.5                                 # so lange leuchtet die Bestätigung


def main(dauer_s=None):                    # dauer_s: nur für den Test, sonst läuft es bis Strg+C
    taster = Button(pinplan.TASTER, pull_up=True)  # interner Pull-up: Ruhe = HIGH, gedrückt = LOW
    led = LED(pinplan.LED_GRUEN)            # grüne Ampel-LED als Status-LED
    zaehler = 0                             # Anzahl der Anforderungen seit Start
    vorher = False                          # Zustand beim letzten Abfragen (False = nicht gedrückt)
    letzte_flanke = 0.0                     # Zeitpunkt des letzten gezählten Drucks
    led_aus_um = 0.0                        # Zeitpunkt, an dem die LED wieder ausgehen soll
    ende = None if dauer_s is None else time.monotonic() + dauer_s  # Testende, im Normalbetrieb None
    print("Materialstation (Polling) bereit. Taster drücken, Strg+C beendet.")  # Startmeldung
    try:                                    # geschützter Block: finally räumt immer auf
        while ende is None or time.monotonic() < ende:  # Endlosschleife (im Test begrenzt): das ist das Polling
            jetzt = time.monotonic()        # monotone Zeit, springt nicht bei Uhrzeitkorrektur
            gedrueckt = taster.is_pressed   # aktuellen Zustand des Tasters lesen
            if gedrueckt and not vorher and jetzt - letzte_flanke > ENTPRELL_S:  # steigende Flanke außerhalb der Sperrzeit
                zaehler += 1                # eine neue Anforderung
                letzte_flanke = jetzt       # Zeitpunkt merken für die Entprellung
                led.on()                    # Bestätigung einschalten
                led_aus_um = jetzt + LED_S  # Ausschaltzeit vormerken, statt mit sleep zu blockieren
                print(f"Materialanforderung {zaehler}")  # Ereignis im Terminal
            vorher = gedrueckt              # Zustand für die nächste Runde merken
            if led.is_lit and jetzt >= led_aus_um:  # Bestätigungszeit abgelaufen?
                led.off()                   # LED aus
            time.sleep(ABFRAGE_S)           # kurz warten, sonst läuft der Prozessor auf 100 %
    except KeyboardInterrupt:               # Strg+C
        print(f"\nBeendet. {zaehler} Anforderungen gezählt.")  # Abschlussmeldung mit Summe
    finally:                                # läuft immer, auch bei Fehlern
        led.off()                           # LED sicher aus
        led.close()                         # GPIO7 freigeben
        taster.close()                      # GPIO27 freigeben
    return zaehler                          # Anzahl zurückgeben, damit der Test sie prüfen kann


if __name__ == "__main__":                  # nur beim direkten Start ausführen, nicht beim Import
    main()                                  # Hauptprogramm starten
