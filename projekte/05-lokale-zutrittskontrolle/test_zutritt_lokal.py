"""Tests für Projekt 05 mit simulierten Pins (ohne Keypad und ohne Servo lauffähig).

Prüft die Testfälle ZT-01 bis ZT-07 aus dem Arbeitsblatt, die Keypad-Scanlogik und
die Servo-Sequenz (Winkel 0 -> 90 -> 0, danach kein Signal mehr).
Aufruf: python3 test_zutritt_lokal.py
"""
import sys                                     # Suchpfad und Exit-Code
import threading                               # Servo-Winkel während der Sequenz mitschreiben
import time                                    # Wartezeiten
from pathlib import Path                       # Pfade

HIER = Path(__file__).resolve().parent         # Ordner dieses Tests
sys.path.insert(0, str(HIER))                  # Projektdatei importierbar
sys.path.insert(0, str(HIER.parent / "gemeinsam"))  # gemeinsame Bausteine

from gpiozero import Device                    # noqa: E402  globale Pin-Fabrik
from gpiozero.pins.mock import MockFactory, MockPWMPin  # noqa: E402  simulierte Pins, auch mit PWM für den Servo

Device.pin_factory = MockFactory(pin_class=MockPWMPin)  # alle Pins simuliert und PWM-fähig

import pinplan                                 # noqa: E402  Pinnummern
import zutritt_ablauf                          # noqa: E402  Hauptschleife
from keypad import Keypad                      # noqa: E402  Scanner
from pin_eingabe import PinEingabe             # noqa: E402  Zustandsautomat
from tuer import OFFEN, VERRIEGELT, Tuer       # noqa: E402  Servo und Rückmeldung
from zutritt_lokal import lokale_pruefung      # noqa: E402  lokale PIN-Prüfung

fehler = 0                                     # Fehlerzähler


def pruefe(name, ok):                          # Ergebniszeile und Zählung
    global fehler                              # globalen Zähler ändern
    print(("OK     " if ok else "FEHLER ") + name)  # Zeile
    fehler += 0 if ok else 1                   # zählen


# ---------- PIN-Eingabe (Zustandsautomat) ----------
e = PinEingabe(timeout_s=10)                   # frische Eingabe
for z in "12345":                              # fünf Ziffern tippen
    r = e.taste(z, 0)                          # jeweils zur Zeit 0
pruefe("ZT-04 fünfte Ziffer wird ignoriert", r == "voll" and e.stellen == 4)  # nur 4 gespeichert
e.taste("*", 1)                                # letzte Ziffer löschen
pruefe("ZT-07 * löscht genau eine Ziffer", e.stellen == 3)  # 3 übrig
pruefe("ZT-03 # bei 3 Ziffern prüft nicht", e.taste("#", 2) == "unvollstaendig")  # keine Prüfung
e.taste("9", 3)                                # vierte Ziffer
r = e.taste("#", 4)                            # bestätigen
pruefe("# bei 4 Ziffern liefert die PIN zur Prüfung", r == ("pruefen", "1239"))  # richtige Reihenfolge
pruefe("Puffer ist nach der Prüfung leer", e.stellen == 0)  # PIN liegt nicht mehr im Speicher
e.taste("1", 10)                               # neue Eingabe beginnt
pruefe("ZT-05 Timeout löscht nach 10 s", e.timeout_pruefen(20.5) and e.stellen == 0)  # 10,5 s später
pruefe("A-D werden ignoriert", e.taste("A", 30) == "ignoriert" and e.stellen == 0)  # keine Funktion

# ---------- Keypad-Scan ----------
kp = Keypad()                                  # Scanner mit simulierten Pins
echte_spalte = kp.spalten[1]                   # Spalte 2 merken, um sie am Ende zu schließen


class KontaktSpalte:                           # simuliert den gedrückten Kontakt zwischen Zeile 2 und Spalte 2
    gedrueckt = True                           # Taste 5 ist gedrückt
    @property                                  # wie das echte is_active lesbar
    def is_active(self):                       # Spalte 2 ist HIGH, wenn Zeile 2 HIGH ist und die Taste gedrückt ist
        return self.gedrueckt and kp.zeilen[1].value == 1  # genau das macht der Kontakt in der Matrix


kontakt = KontaktSpalte()                      # Ersatz-Spalte anlegen
kp.spalten[1] = kontakt                        # Spalte 2 durch die Simulation ersetzen
pruefe("Scan erkennt Taste 5 (R2/C2)", kp.taste() == "5")  # richtige Zuordnung
pruefe("langer Druck zählt nur einmal", kp.taste() is None)  # noch gedrückt: keine Wiederholung
kontakt.gedrueckt = False                      # Taste loslassen
kp.taste()                                     # Loslassen erkennen
kontakt.gedrueckt = True                       # erneut drücken
pruefe("nach dem Loslassen zählt ein neuer Druck", kp.taste() == "5")  # wieder erkannt
kp.spalten[1] = echte_spalte                   # echte Spalte zurück, damit sie geschlossen wird
kp.schliessen()                                # Pins freigeben

# ---------- Tür und Hauptschleife ----------
tuer = Tuer(fabrik=None)                       # Servo mit Mock-PWM
pruefe("SV-01 Start verriegelt, danach kein Signal", tuer.servo.value is None)  # detach() nach Startposition
winkel = []                                    # aufgezeichnete Servo-Winkel
stop = threading.Event()                       # beendet die Aufzeichnung
def aufzeichnen():                             # schreibt jede Winkeländerung mit
    while not stop.is_set():                   # bis Stop
        w = tuer.servo.angle                   # aktueller Sollwinkel (None = kein Signal)
        if not winkel or winkel[-1] != w:      # nur Änderungen merken
            winkel.append(w)                   # merken
        time.sleep(0.02)                       # 20 ms Takt
threading.Thread(target=aufzeichnen, daemon=True).start()  # Aufzeichnung starten


class FakeKeypad:                              # liefert eine feste Tastenfolge statt echter Tasten
    def __init__(self, folge):                 # folge: Text mit Tasten
        self.folge = list(folge)               # als Liste
    def taste(self):                           # wie Keypad.taste()
        return self.folge.pop(0) if self.folge else None  # nächste Taste oder nichts


pruefung = lokale_pruefung("4711")             # Soll-PIN nur für den Test
kp = FakeKeypad("0000#")                       # ZT-02: falsche PIN
zutritt_ablauf.ausfuehren(kp, tuer, pruefung, laufen=lambda: bool(kp.folge))  # bis die Folge abgearbeitet ist
time.sleep(0.3)                                # Aufzeichnung nachlaufen lassen
pruefe("ZT-02 falsche PIN bewegt den Servo nicht", all(w in (None, VERRIEGELT) for w in winkel))  # nie 90°
pruefe("ZT-02 rote LED leuchtet", tuer.rot.is_lit)  # rot 1 s
kp = FakeKeypad("4711#")                       # ZT-01: richtige PIN
zutritt_ablauf.ausfuehren(kp, tuer, pruefung, laufen=lambda: bool(kp.folge))  # öffnet und verriegelt wieder (ca. 4,2 s)
time.sleep(0.3)                                # nachlaufen lassen
stop.set()                                     # Aufzeichnung beenden
pruefe("ZT-01 richtige PIN: Servo fährt 90° und zurück auf 0°", OFFEN in winkel and winkel.index(OFFEN) < len(winkel) - 1 and VERRIEGELT in winkel[winkel.index(OFFEN):])  # Reihenfolge
pruefe("ZT-01 danach PWM aus und grün aus", tuer.servo.value is None and not tuer.gruen.is_lit)  # Endzustand
tuer.schliessen()                              # Cleanup

print()                                        # Leerzeile
print("Alle Tests bestanden." if fehler == 0 else f"{fehler} Test(s) fehlgeschlagen.")  # Fazit
sys.exit(1 if fehler else 0)                   # Exit-Code
