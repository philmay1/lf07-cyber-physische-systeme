#!/usr/bin/env python3
"""SENTINEL Zutrittskontrolle: PIN am 4x4-Keypad, Sperre nach 3 Fehlversuchen.

Start:
    python3 zutritt.py               Keypad + Ampel-LEDs + Summer
    python3 zutritt.py --tastatur    PIN über die PC-Tastatur (SSH), LEDs und Summer echt
    python3 zutritt.py --tasten-test zeigt nur, welche Keypad-Taste gedrückt wird

Bedienung: Ziffern tippen, # bestätigt, * löscht die Eingabe.
"""
import argparse
import sys
import threading
import time

from gpiozero import LED, Buzzer, Button, OutputDevice

import zutritt_db as db

# Keypad: Pin 1 bis 4 = Zeilen, Pin 5 bis 8 = Spalten (von links gezählt)
ZEILEN = [5, 6, 13, 19]       # physische Pins 29, 31, 33, 35
SPALTEN = [26, 16, 20, 21]    # physische Pins 37, 36, 38, 40
TASTEN = ["1", "2", "3", "A",
          "4", "5", "6", "B",
          "7", "8", "9", "C",
          "*", "0", "#", "D"]

# Anzeige: die Auto-Ampel aus Tag 3 bleibt gesteckt
LED_ROT, LED_GELB, LED_GRUEN, SUMMER = 25, 8, 7, 18
TUER_OFFEN = 3                # so lange bleibt grün an (Sekunden)
EINGABE_TIMEOUT = 10          # angefangene Eingabe verfällt nach 10 s ohne Taste


class Keypad:
    """Matrix-Abfrage: eine Zeile nach der anderen auf HIGH, dann Spalten lesen."""

    def __init__(self):
        self.zeilen = [OutputDevice(p, initial_value=False) for p in ZEILEN]
        self.spalten = [Button(p, pull_up=False) for p in SPALTEN]   # interner Pull-down

    def gedrueckt(self):
        for z, zeile in enumerate(self.zeilen):
            zeile.on()
            time.sleep(0.001)                       # Leitung kurz einschwingen lassen
            for s, spalte in enumerate(self.spalten):
                if spalte.is_pressed:
                    zeile.off()
                    return TASTEN[z * 4 + s]
            zeile.off()
        return None

    def tasten(self):
        """Liefert jede Taste genau einmal pro Druck (wartet aufs Loslassen = entprellen)."""
        letzte = None
        while True:
            t = self.gedrueckt()
            if t and t != letzte:
                yield t
            letzte = t
            time.sleep(0.02)

    def close(self):
        for g in self.zeilen + self.spalten:
            g.close()


class Anzeige:
    def __init__(self):
        self.rot, self.gelb, self.gruen = LED(LED_ROT), LED(LED_GELB), LED(LED_GRUEN)
        self.summer = Buzzer(SUMMER, active_high=False)   # PNP-Transistor: LOW = Ton
        self.sperre = threading.Lock()   # damit Wächter und Signale sich nicht ins Wort fallen

    def klick(self):
        self.gelb.blink(0.06, 0, n=1)
        self.summer.beep(0.03, 0, n=1)

    def offen(self):
        with self.sperre:
            self.rot.off()
            self.summer.beep(0.08, 0.08, n=2)
            self.gruen.on()
            time.sleep(TUER_OFFEN)
            self.gruen.off()

    def falsch(self):
        with self.sperre:
            self.summer.beep(0.5, 0, n=1)
            self.rot.blink(0.15, 0.15, n=3, background=False)

    def alarm(self):
        with self.sperre:
            self.summer.beep(0.3, 0.2, n=4)
            self.rot.blink(0.1, 0.1, n=10, background=False)
            self.rot.on()

    def close(self):
        for g in (self.rot, self.gelb, self.gruen, self.summer):
            g.close()


class Zutritt:
    """Die eigentliche Logik. Kennt keine Pins, nur Tasten rein und Anzeige raus."""

    def __init__(self, anzeige, con, ausgabe=print):
        self.anzeige, self.con, self.ausgabe = anzeige, con, ausgabe
        self.eingabe = ""
        self.letzte_taste = 0.0

    def taste(self, t):
        st = db.status(self.con)
        if st["gesperrt"]:
            self.ausgabe(f"Gesperrt, noch {st['rest']:.0f} s. Taste ignoriert.")
            self.anzeige.rot.on()
            return "gesperrt"
        if time.time() - self.letzte_taste > EINGABE_TIMEOUT:
            self.eingabe = ""
        self.letzte_taste = time.time()
        self.anzeige.klick()
        if t == "*":
            self.eingabe = ""
            self.ausgabe("Eingabe gelöscht")
            return "geloescht"
        if t == "#":
            return self.bestaetigen()
        if t.isdigit() and len(self.eingabe) < 8:
            self.eingabe += t
            self.ausgabe("PIN: " + "*" * len(self.eingabe))
        return "eingabe"

    def bestaetigen(self):
        pin, self.eingabe = self.eingabe, ""
        benutzer = db.pin_pruefen(self.con, pin) if pin else None
        ergebnis = db.versuch_eintragen(self.con, benutzer is not None, benutzer)
        if ergebnis == "ok":
            self.ausgabe(f"Zutritt für {benutzer['name']}")
            self.anzeige.offen()
        elif ergebnis == "falsch":
            st = db.status(self.con)
            self.ausgabe(f"Falsche PIN ({st['fehlversuche']} von {db.MAX_FEHLVERSUCHE})")
            self.anzeige.falsch()
        else:
            st = db.status(self.con)
            self.ausgabe(f"3 Fehlversuche: GESPERRT für {st['rest']:.0f} s")
            self.anzeige.alarm()
        return ergebnis


def sperr_waechter(anzeige, stopp):
    """Hält die rote LED an, solange gesperrt ist, und schaltet sie danach aus.
    Merkt so auch, wenn jemand im Dashboard entsperrt."""
    con = db.verbinden()
    war_gesperrt = None
    while not stopp.is_set():
        gesperrt = db.status(con)["gesperrt"]
        if gesperrt != war_gesperrt:
            with anzeige.sperre:
                anzeige.rot.value = gesperrt
            if war_gesperrt and not gesperrt:
                print("Sperre aufgehoben, Eingabe wieder möglich")
            war_gesperrt = gesperrt
        stopp.wait(0.5)


def tastatur_tasten():
    print("Tastatur-Modus: Ziffern, # bestätigt, * löscht. Enter schickt die Zeile ab. Strg+C beendet.")
    for zeile in sys.stdin:
        for t in zeile.strip().upper():
            if t in TASTEN:
                yield t


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tastatur", action="store_true", help="PIN über die Tastatur statt Keypad")
    p.add_argument("--tasten-test", action="store_true", help="nur Keypad-Tasten anzeigen")
    a = p.parse_args()

    if a.tasten_test:
        kp = Keypad()
        print("Drück Tasten auf dem Keypad, Strg+C beendet.")
        try:
            for t in kp.tasten():
                print("Taste:", t)
        except KeyboardInterrupt:
            pass
        finally:
            kp.close()
        return

    con = db.verbinden()
    if not con.execute("SELECT 1 FROM benutzer").fetchone():
        print("Noch keine Benutzer. Erst anlegen: python3 verwalten.py neu <name>")
        return
    anzeige = Anzeige()
    kp = None if a.tastatur else Keypad()
    stopp = threading.Event()
    threading.Thread(target=sperr_waechter, args=(anzeige, stopp), daemon=True).start()
    zutritt = Zutritt(anzeige, con)
    print("SENTINEL Zutrittskontrolle bereit.")
    try:
        for t in (tastatur_tasten() if a.tastatur else kp.tasten()):
            zutritt.taste(t)
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        stopp.set()
        anzeige.close()
        if kp:
            kp.close()


if __name__ == "__main__":
    main()
