"""Tests für Projekt 04: Zustandslogik mit künstlicher Zeit (kein Warten, keine Hardware).

Deckt die Pflichtnachweise des Arbeitsblatts ab: SM-03 Abbruch, SM-04/05 genau ein
Alarm, SM-06/07 Wieder-Scharfschaltung und zweiter Vorfall, SM-11 Sensorfehler.
Aufruf: python3 test_klimapruefraum.py
"""
import sys                                     # Suchpfad und Exit-Code
from pathlib import Path                       # Pfade

HIER = Path(__file__).resolve().parent         # Ordner dieses Tests
sys.path.insert(0, str(HIER))                  # Projektdatei importierbar
sys.path.insert(0, str(HIER.parent / "gemeinsam"))  # gemeinsame Bausteine

import klimapruefraum as k                     # noqa: E402  die zu testende Logik

fehler = 0                                     # Fehlerzähler


def pruefe(name, ok):                          # Ergebniszeile und Zählung
    global fehler                              # globalen Zähler ändern
    print(("OK     " if ok else "FEHLER ") + name)  # Zeile
    fehler += 0 if ok else 1                   # zählen


gesendet = []                                  # hier landen die "gesendeten" Alarme
w = k.Raumwaechter(0.0, lambda still: gesendet.append(still))  # Start bei Zeit 0


def laufen(von, bis, bewegung=False, schritt=0.05):  # simuliert die Hauptschleife über einen Zeitraum
    t = von                                    # Startzeit
    while t < bis:                             # bis zur Endzeit
        w.schritt(t, bewegung)                 # Logik weiterschalten
        t += schritt                           # 50 ms weiter
    return w.zustand                           # Zustand am Ende


pruefe("SM-01 Start in Überwachung", laufen(0, 5) == k.UEBERWACHUNG)  # nach 5 s still: noch kein Countdown
pruefe("SM-02 Countdown ab 6 s Stille", laufen(5, 7) == k.COUNTDOWN)  # 15 - 9 = 6 s
pruefe("Countdown zeigt 9 bei 6,5 s", w.rest(6.5) == 9)  # Anzeige rundet auf
w.schritt(7.0, True)                           # SM-03: Bewegung mitten im Countdown
pruefe("SM-03 Bewegung bricht Countdown sofort ab", w.zustand == k.UEBERWACHUNG and not gesendet)  # kein Alarm
pruefe("SM-04 Alarm genau nach 15 s Stille", laufen(7.05, 22.1) == k.ALARMIERT and len(gesendet) == 1)  # 7 + 15 = 22
laufen(22.1, 60)                               # SM-05: noch lange still weiter
pruefe("SM-05 kein zweiter Alarm im selben Vorfall", len(gesendet) == 1)  # Einmal-Alarm
w.schritt(60.0, True)                          # SM-06: jemand bewegt sich
pruefe("SM-06 Bewegung schaltet wieder scharf", w.zustand == k.UEBERWACHUNG and not w.alarm_gesendet)  # Flag zurück
laufen(60.05, 76)                              # SM-07: zweiter vollständiger Vorfall
pruefe("SM-07 zweiter Vorfall erzeugt genau einen weiteren Alarm", len(gesendet) == 2)  # jetzt zwei
laufen(76, 76 + k.DAUER_HIGH_S + 1, bewegung=True)  # SM-11: Sensor hängt auf HIGH
pruefe("SM-11 Dauer-HIGH wird als Sensorfehler erkannt", w.zustand == k.FEHLER)  # Diagnosezustand
pruefe("SM-11 kein Alarm durch den Sensorfehler", len(gesendet) == 2)  # keine falsche Alarmierung

print()                                        # Leerzeile
print("Alle Tests bestanden." if fehler == 0 else f"{fehler} Test(s) fehlgeschlagen.")  # Fazit
sys.exit(1 if fehler else 0)                   # Exit-Code
