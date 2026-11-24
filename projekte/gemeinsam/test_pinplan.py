"""Prüft den zentralen Pinplan: kein GPIO doppelt, keine reservierten Pins belegt.

Aufruf: python3 test_pinplan.py
"""
import sys                                     # Exit-Code

import pinplan                                 # der zu prüfende Pinplan

RESERVIERT = {2, 3, 14, 15}                    # I2C (2, 3) und serielle Konsole (14, 15) bleiben frei
pins = list(pinplan.ALLE.values())             # alle vergebenen GPIO-Nummern
doppelt = {p for p in pins if pins.count(p) > 1}  # Pins, die mehr als einmal vorkommen
fehler = 0                                     # Fehlerzähler
print(("OK     " if not doppelt else "FEHLER ") + f"kein GPIO doppelt vergeben {sorted(doppelt) or ''}")  # Ergebnis 1
fehler += 1 if doppelt else 0                  # zählen
belegt = RESERVIERT & set(pins)                # reservierte Pins, die trotzdem belegt sind
print(("OK     " if not belegt else "FEHLER ") + f"I2C und serielle Konsole bleiben frei {sorted(belegt) or ''}")  # Ergebnis 2
fehler += 1 if belegt else 0                   # zählen
print("Alle Tests bestanden." if fehler == 0 else f"{fehler} Test(s) fehlgeschlagen.")  # Fazit
sys.exit(1 if fehler else 0)                   # Exit-Code
