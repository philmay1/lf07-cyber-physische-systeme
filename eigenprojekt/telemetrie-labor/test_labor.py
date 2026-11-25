#!/usr/bin/env python3
"""Test für das Telemetrie-Labor, ohne echte iRacing-Dateien.

Start:  python3 test_labor.py

Der Test baut selbst eine kleine .ibt-Datei im echten Format: ein Auto fährt drei Runden
auf einer Kreisbahn, jede genau 60 s lang, in Runde 3 kurz in die Boxengasse. Dazu stehen
zwei fremde Fahrer in den Session-Infos, um den Datenschutz zu prüfen.
"""
import os
import struct
import tempfile
from pathlib import Path

import numpy as np

# Wegwerf-Datenbank, bevor die Module geladen werden.
TMP = Path(tempfile.mkdtemp())
os.environ["LABOR_DB"] = str(TMP / "labor_test.db")
os.environ["LABOR_PASSWORT_HASH"] = ""

import ibt_lesen      # noqa: E402
import labor_db       # noqa: E402
import labor          # noqa: E402

ok = 0


def pruefe(bedingung, text):
    global ok
    assert bedingung, "FEHLER: " + text
    ok += 1
    print("ok  ", text)


# Kanäle der Test-Datei: (Name, Typ laut iRacing, numpy-Typ).
KANAELE = [("SessionTime", 5, "<f8"), ("Lap", 2, "<i4"), ("LapDistPct", 4, "<f4"), ("Speed", 4, "<f4"),
           ("Throttle", 4, "<f4"), ("Brake", 4, "<f4"), ("Gear", 2, "<i4"), ("RPM", 4, "<f4"),
           ("SteeringWheelAngle", 4, "<f4"), ("Lat", 5, "<f8"), ("Lon", 5, "<f8"), ("FuelLevel", 4, "<f4"),
           ("OnPitRoad", 1, "u1"), ("IsOnTrack", 1, "u1"), ("PlayerTrackSurface", 2, "<i4")]

INFO = """---
WeekendInfo:
 TrackDisplayName: Testring
 TrackConfigName: Kreis
 TrackLength: 3.0000 km
 EventType: Practice
DriverInfo:
 DriverCarIdx: 1
 Drivers:
 - CarIdx: 0
   UserName: Fremder Fahrer
   UserID: 111111
   CarScreenName: Fremdes Auto
 - CarIdx: 1
   UserName: Ich Selbst
   UserID: 222222
   CarScreenName: Testwagen GT3
 - CarIdx: 2
   UserName: Noch Jemand
   UserID: 333333
   CarScreenName: Fremdes Auto
...
"""


# Baut eine .ibt-Datei: Anfahrt (halbe Runde), dann 3 volle Runden à 60 s, dann eine halbe Runde.
def ibt_bauen(pfad):
    takt, rundenzeit = 60, 60.0
    n = int((0.5 + 3 + 0.5) * rundenzeit * takt)
    t = np.arange(n) / takt
    weg = 0.5 + t / rundenzeit                   # Runden seit Start, beginnt bei halber Runde
    lap = np.floor(weg).astype("i4")
    pct = (weg - lap).astype("f4")
    winkel = pct.astype("f8") * 2 * np.pi
    daten = {
        "SessionTime": t, "Lap": lap, "LapDistPct": pct, "Speed": np.full(n, 50.0),
        "Throttle": np.full(n, 1.0), "Brake": np.zeros(n), "Gear": np.full(n, 4), "RPM": np.full(n, 6000.0),
        "SteeringWheelAngle": np.full(n, 0.1), "Lat": 50 + 0.01 * np.sin(winkel), "Lon": 8 + 0.01 * np.cos(winkel),
        "FuelLevel": 60 - t / 60, "OnPitRoad": ((lap == 3) & (pct > 0.4) & (pct < 0.45)).astype("u1"),
        "IsOnTrack": np.ones(n), "PlayerTrackSurface": np.full(n, 3),
    }
    # Datensatz-Aufbau: Kanäle hintereinander.
    namen, formate, offsets, off = [], [], [], 0
    for name, _, fmt in KANAELE:
        namen.append(name); formate.append(fmt); offsets.append(off); off += np.dtype(fmt).itemsize
    satz = np.dtype({"names": namen, "formats": formate, "offsets": offsets, "itemsize": off})
    saetze = np.zeros(n, dtype=satz)
    for name in namen:
        saetze[name] = daten[name]
    info = INFO.encode("cp1252")
    var_off = 144
    info_off = var_off + 144 * len(KANAELE)
    daten_off = info_off + len(info)
    kopf = struct.pack("<10i", 2, 1, takt, 1, len(info), info_off, len(KANAELE), var_off, 1, off)
    kopf += struct.pack("<2i", 0, 0) + struct.pack("<4i", n, daten_off, 0, 0) + b"\0" * 48
    kopf += struct.pack("<qddii", 1764000000, 0.0, float(t[-1]), 3, n)
    variablen = b""
    for (name, typ, _), o in zip(KANAELE, offsets):
        variablen += struct.pack("<3i", typ, o, 1) + b"\0" * 4 + name.encode().ljust(32, b"\0") + b"\0" * 96
    Path(pfad).write_bytes(kopf + variablen + info + saetze.tobytes())


datei = TMP / "testwagen_testring.ibt"
ibt_bauen(datei)

# 1. Datei lesen
session, runden = ibt_lesen.datei_auswerten(str(datei))
pruefe(session["strecke"] == "Testring" and session["laenge_m"] == 3000, "Strecke und Länge aus den Session-Infos")
pruefe(session["auto"] == "Testwagen GT3", "eigenes Auto über DriverCarIdx gefunden")
pruefe("Fremder" not in str(session) and "111111" not in str(session), "keine fremden Fahrer in den gespeicherten Angaben")
pruefe(len(runden) == 3, "drei volle Runden erkannt (Anfahrt und Rest nicht)")
pruefe(all(abs(r["zeit"] - 60.0) < 0.002 for r in runden), "Rundenzeit 60,000 s auf 2 ms genau")
pruefe(runden[0]["gueltig"] and not runden[2]["gueltig"] and runden[2]["grund"] == "Box", "Runde mit Boxengasse ist ungültig")
k = runden[0]["kanaele"]
pruefe(len(k["speed"]) == ibt_lesen.PUNKTE and abs(k["speed"][500] - 180) < 0.1, "1000 Punkte pro Runde, 50 m/s = 180 km/h")
pruefe(abs(k["t"][500] - 30.0) < 0.02, "halbe Runde nach 30 s")
pruefe(abs(runden[0]["sprit"] - 1.0) < 0.01, "Spritverbrauch 1 l pro Runde")

# 2. Datenbank
con = labor_db.verbinden()
sid = labor_db.speichern(con, dict(session, datum="2026-11-25 12:00"), runden, datei.name)
pruefe(labor_db.sitzungen(con)[0]["gueltige"] == 2, "Sitzungsliste zählt 2 saubere Runden")
r = labor_db.runde(con, labor_db.sitzung(con, sid)["runden"][0]["id"])
pruefe(len(r["kanaele"]["lat"]) == 1000 and r["strecke"] == "Testring", "Runde mit Kurven aus der DB entpackt")
pruefe(labor_db.bestenliste(con)[0]["auto"] == "Testwagen GT3", "Bestenliste")

# 3. Web-API
web = labor.app.test_client()
pruefe(web.get("/api/status").get_json()["darf_aendern"], "ohne Passwort: Ändern nur lokal erlaubt (Test läuft lokal)")
with open(datei, "rb") as f:
    antwort = web.post("/api/upload", data={"datei": (f, datei.name)}, content_type="multipart/form-data")
pruefe(antwort.status_code == 200 and antwort.get_json()["ok"], "Upload über die API")
pruefe(len(web.get("/api/sitzungen").get_json()) == 2, "zweite Sitzung gespeichert")
pruefe(web.get("/api/upload").status_code == 405, "Upload nur per POST")
fremd = web.get("/api/status", environ_base={"REMOTE_ADDR": "192.168.1.50"}).get_json()
pruefe(not fremd["darf_aendern"], "ohne Passwort darf ein anderer Rechner nichts ändern")

# 4. Login
labor.PASSWORT_HASH = labor.hash_bilden("richtig-geheim")
pruefe(not labor.passwort_ok("falsch", labor.PASSWORT_HASH) and labor.passwort_ok("richtig-geheim", labor.PASSWORT_HASH), "Passwort-Hash prüft richtig")
pruefe("richtig-geheim" not in labor.PASSWORT_HASH, "Passwort steht nicht im Hash")
pruefe(web.delete(f"/api/sitzung/{sid}").status_code == 401, "Löschen ohne Login verboten")
pruefe(web.post("/api/login", json={"passwort": "falsch"}).status_code == 403, "falsches Passwort abgelehnt")
pruefe(web.post("/api/login", json={"passwort": "richtig-geheim"}).get_json()["ok"], "richtiges Passwort angenommen")
pruefe(web.delete(f"/api/sitzung/{sid}").get_json()["ok"], "nach Login: Löschen erlaubt")
pruefe(len(web.get("/api/sitzungen").get_json()) == 1, "Sitzung samt Runden gelöscht")
pruefe(b"Telemetrie-Labor" in web.get("/").data and web.get("/static/uPlot.iife.min.js").status_code == 200, "Oberfläche und uPlot werden ausgeliefert")

print(f"\nAlle {ok} Prüfungen bestanden.")
