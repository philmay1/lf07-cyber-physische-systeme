"""4x4-Matrix-Keypad mit 8 Leitungen auslesen (Scanverfahren aus Tag 5, AB1).

Die Zeilen sind Ausgänge, die Spalten Eingänge mit internem Pull-down.
Das Programm schaltet eine Zeile nach der anderen auf HIGH und schaut, welche Spalte
dabei HIGH wird. Zeile 2 und Spalte 2 heißt: Taste 5.
"""
import time                                      # kurze Pausen beim Scannen

from gpiozero import DigitalInputDevice, DigitalOutputDevice  # einfache Ein- und Ausgänge

import pinplan                                   # Pins und Tastenbelegung aus dem zentralen Pinplan


class Keypad:                                    # kapselt das Scannen, damit Projekte nur "welche Taste?" fragen
    def __init__(self, zeilen=pinplan.KEYPAD_ZEILEN, spalten=pinplan.KEYPAD_SPALTEN, tasten=pinplan.KEYPAD_TASTEN):  # Pins und Tasten sind einstellbar, Standard ist der Pinplan
        self.zeilen = [DigitalOutputDevice(p, initial_value=False) for p in zeilen]  # Zeilen als Ausgang, starten auf LOW
        self.spalten = [DigitalInputDevice(p, pull_up=False) for p in spalten]       # Spalten als Eingang, Pull-down hält sie LOW
        self.tasten = tasten                     # Tastenbelegung merken
        self.gedrueckt = None                    # zuletzt gemeldete Taste, damit ein langer Druck nur einmal zählt

    def scannen(self):                           # ein kompletter Durchlauf über alle 16 Tasten
        treffer = []                             # alle gedrückten Tasten dieses Durchlaufs
        for z, zeile in enumerate(self.zeilen):  # jede Zeile nacheinander
            zeile.on()                           # diese Zeile auf HIGH legen
            time.sleep(0.001)                    # 1 ms warten, bis die Spannung stabil anliegt
            for s, spalte in enumerate(self.spalten):  # alle Spalten abfragen
                if spalte.is_active:             # Spalte ist HIGH: Taste an Kreuzung (z, s) gedrückt
                    treffer.append(self.tasten[z][s])  # Taste merken
            zeile.off()                          # Zeile ausschalten, nächste Zeile prüfen
        if len(treffer) == 1:                    # genau eine Taste: eindeutig
            return treffer[0]                    # diese Taste zurückgeben
        return None                              # keine oder mehrere Tasten: mehrdeutig, wird abgelehnt (AB3 6.5)

    def taste(self):                             # liefert eine Taste genau einmal pro Druck
        aktuell = self.scannen()                 # aktuelle Taste (oder None)
        if aktuell == self.gedrueckt:            # gleiche Taste wie beim letzten Scan: noch gedrückt
            return None                          # nicht erneut melden, sonst entstehen Zifferketten
        self.gedrueckt = aktuell                 # neuen Zustand merken (auch None = losgelassen)
        return aktuell                           # neue Taste melden (oder None)

    def schliessen(self):                        # alle 8 Pins freigeben
        for geraet in self.zeilen + self.spalten:  # Zeilen und Spalten zusammen durchgehen
            geraet.close()                       # Pin an das System zurückgeben
