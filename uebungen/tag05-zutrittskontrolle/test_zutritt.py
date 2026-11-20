#!/usr/bin/env python3
"""Test ohne Hardware: simulierte Pins (gpiozero MockFactory) und eine Test-Datenbank.

    python3 test_zutritt.py
"""
# Der Docstring oben wird nicht ausgeführt. Er sagt, wie man den Test startet.

# os setzt eine Umgebungsvariable, damit gpiozero nur simulierte Pins benutzt.
import os

# tempfile legt einen Wegwerf-Ordner für die Test-Datenbank an.
import tempfile

# time.sleep, um auf das Ende einer Sperre zu warten.
import time

# Path baut den Pfad zur Test-Datenbank.
from pathlib import Path

# WICHTIG: muss vor dem Import von gpiozero stehen. "mock" heißt: keine echten Pins, nur Simulation.
os.environ["GPIOZERO_PIN_FACTORY"] = "mock"
# Unsere Datenbank-Datei laden.
import zutritt_db as db                                # noqa: E402
# Die Test-Datenbank liegt in einem temporären Ordner. Die echte zutritt.db bleibt unberührt.
db.DB_DATEI = Path(tempfile.mkdtemp()) / "test.db"
# Sperre im Test nur 5 s statt 60 s, sonst dauert der Test ewig. Der Alarm selbst dauert 2 s.
db.SPERRE_START = 5
# Das Hauptprogramm laden (main() startet dabei nicht, siehe if __name__ == "__main__").
import zutritt as z                                    # noqa: E402
# Grün im Test nur 0,1 s statt 3 s.
z.TUER_OFFEN = 0.1

# Zählt die fehlgeschlagenen Prüfungen.
fehler = 0


# Gibt OK oder FEHLER aus und zählt Fehler mit.
def pruefe(text, bedingung):
    # "global": wir ändern die Variable fehler von oben, keine neue lokale.
    global fehler
    # OK bei wahrer Bedingung, sonst FEHLER, danach der Beschreibungstext.
    print(("OK    " if bedingung else "FEHLER"), text)
    # True zählt als 1, False als 0. "not bedingung" ist also 1 bei einem Fehler.
    fehler += not bedingung


# Tippt eine Tastenfolge wie "2468#" und gibt das Ergebnis der letzten Taste zurück.
def tippen(zutritt, folge):
    ergebnis = None
    # Jedes Zeichen als einzelnen Tastendruck an die Logik geben.
    for t in folge:
        ergebnis = zutritt.taste(t)
    return ergebnis


# Test-Datenbank öffnen (wird dabei angelegt).
con = db.verbinden()
# Zwei Test-Benutzer anlegen: einen normalen und einen Admin.
db.benutzer_anlegen(con, "Test", "2468")
db.benutzer_anlegen(con, "Chef", "1357", "admin")
# Die Datei als rohe Bytes lesen: Die PIN darf darin nirgends im Klartext stehen.
pruefe("PIN steht nicht im Klartext in der DB",
       b"2468" not in Path(db.DB_DATEI).read_bytes())

# Anzeige mit simulierten LEDs und Summer.
anzeige = z.Anzeige()
# Die Logik. ausgabe=lambda: Meldungen werden im Test verschluckt, damit die Ausgabe übersichtlich bleibt.
zt = z.Zutritt(anzeige, con, ausgabe=lambda *_: None)

# Die eigentlichen Prüfungen, eine pro Zeile.
pruefe("richtige PIN öffnet", tippen(zt, "2468#") == "ok")
pruefe("* löscht die Eingabe", tippen(zt, "99*2468#") == "ok")
pruefe("1. falsche PIN", tippen(zt, "1111#") == "falsch")
pruefe("2. falsche PIN", tippen(zt, "2222#") == "falsch")
pruefe("3. falsche PIN sperrt", tippen(zt, "3333#") == "gesperrt")
pruefe("rote LED leuchtet bei Sperre", anzeige.rot.is_lit)
pruefe("während der Sperre geht auch die richtige PIN nicht", tippen(zt, "2468#") == "gesperrt")

# Eine neue Verbindung tut so, als wäre der Pi neu gestartet.
neu = db.verbinden()
pruefe("Sperre übersteht einen Neustart", db.status(neu)["gesperrt"])

# Warten, bis die 5-Sekunden-Sperre abgelaufen ist.
time.sleep(db.SPERRE_START + 0.2)
pruefe("nach Ablauf wieder frei", not db.status(con)["gesperrt"])
# Zwei Fehler tippen (eine Ziffer reicht als falsche PIN) ...
tippen(zt, "1#2#")
# ... der dritte löst die zweite Sperre aus. Die muss länger als die erste sein (Stufe 2 = 10 s).
pruefe("zweite Sperre ist doppelt so lang", tippen(zt, "3#") == "gesperrt"
       and db.status(con)["rest"] > db.SPERRE_START * 1.2)

# Jetzt das Dashboard testen, ohne echten Webserver: Flask bringt einen Test-Client mit.
import dashboard                                       # noqa: E402
web = dashboard.app.test_client()
pruefe("Dashboard zeigt Sperre", web.get("/api/status").get_json()["gesperrt"])
# 2468 ist die PIN eines normalen Benutzers, kein Admin: muss abgelehnt werden (HTTP 403).
pruefe("falsche Admin-PIN wird abgelehnt", web.post("/api/entsperren", json={"pin": "2468"}).status_code == 403)
# 1357 ist der Admin: muss klappen (HTTP 200).
pruefe("Admin entsperrt per Dashboard", web.post("/api/entsperren", json={"pin": "1357"}).status_code == 200)
pruefe("danach wieder frei", not db.status(con)["gesperrt"])
pruefe("richtige PIN nach Entsperren", tippen(zt, "2468#") == "ok")
pruefe("Protokoll hat Einträge", len(db.letzte_versuche(con, 50)) >= 10)
pruefe("Startseite des Dashboards lädt", b"SENTINEL" in web.get("/").data)

# Simulierte Pins freigeben.
anzeige.close()
# Zusammenfassung ausgeben.
print("\nAlle Tests bestanden." if not fehler else f"\n{fehler} Test(s) fehlgeschlagen.")
# Rückgabewert fürs Betriebssystem: 0 = alles gut, 1 = Fehler.
raise SystemExit(1 if fehler else 0)
