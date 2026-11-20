#!/usr/bin/env python3
"""Test ohne Hardware: simulierte Pins (gpiozero MockFactory) und eine Test-Datenbank.

    python3 test_zutritt.py
"""
import os
import tempfile
import time
from pathlib import Path

os.environ["GPIOZERO_PIN_FACTORY"] = "mock"
import zutritt_db as db                                # noqa: E402
db.DB_DATEI = Path(tempfile.mkdtemp()) / "test.db"     # echte zutritt.db bleibt unberührt
db.SPERRE_START = 5                                    # kurze Sperre fürs Testen (Alarm dauert 2 s)
import zutritt as z                                    # noqa: E402
z.TUER_OFFEN = 0.1

fehler = 0


def pruefe(text, bedingung):
    global fehler
    print(("OK    " if bedingung else "FEHLER"), text)
    fehler += not bedingung


def tippen(zutritt, folge):
    ergebnis = None
    for t in folge:
        ergebnis = zutritt.taste(t)
    return ergebnis


con = db.verbinden()
db.benutzer_anlegen(con, "Test", "2468")
db.benutzer_anlegen(con, "Chef", "1357", "admin")
pruefe("PIN steht nicht im Klartext in der DB",
       b"2468" not in Path(db.DB_DATEI).read_bytes())

anzeige = z.Anzeige()
zt = z.Zutritt(anzeige, con, ausgabe=lambda *_: None)

pruefe("richtige PIN öffnet", tippen(zt, "2468#") == "ok")
pruefe("* löscht die Eingabe", tippen(zt, "99*2468#") == "ok")
pruefe("1. falsche PIN", tippen(zt, "1111#") == "falsch")
pruefe("2. falsche PIN", tippen(zt, "2222#") == "falsch")
pruefe("3. falsche PIN sperrt", tippen(zt, "3333#") == "gesperrt")
pruefe("rote LED leuchtet bei Sperre", anzeige.rot.is_lit)
pruefe("während der Sperre geht auch die richtige PIN nicht", tippen(zt, "2468#") == "gesperrt")

neu = db.verbinden()                                   # wie nach einem Neustart
pruefe("Sperre übersteht einen Neustart", db.status(neu)["gesperrt"])

time.sleep(db.SPERRE_START + 0.2)
pruefe("nach Ablauf wieder frei", not db.status(con)["gesperrt"])
tippen(zt, "1#2#")
pruefe("zweite Sperre ist doppelt so lang", tippen(zt, "3#") == "gesperrt"
       and db.status(con)["rest"] > db.SPERRE_START * 1.2)

import dashboard                                       # noqa: E402
web = dashboard.app.test_client()
pruefe("Dashboard zeigt Sperre", web.get("/api/status").get_json()["gesperrt"])
pruefe("falsche Admin-PIN wird abgelehnt", web.post("/api/entsperren", json={"pin": "2468"}).status_code == 403)
pruefe("Admin entsperrt per Dashboard", web.post("/api/entsperren", json={"pin": "1357"}).status_code == 200)
pruefe("danach wieder frei", not db.status(con)["gesperrt"])
pruefe("richtige PIN nach Entsperren", tippen(zt, "2468#") == "ok")
pruefe("Protokoll hat Einträge", len(db.letzte_versuche(con, 50)) >= 10)

anzeige.close()
print("\nAlle Tests bestanden." if not fehler else f"\n{fehler} Test(s) fehlgeschlagen.")
raise SystemExit(1 if fehler else 0)
