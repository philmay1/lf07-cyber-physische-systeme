"""Datenbank des Telemetrie-Labors (SQLite, Datei labor.db).

Zwei Tabellen:
    sitzung   eine hochgeladene .ibt-Datei: Strecke, Auto, Datum, Art der Session
    runde     jede Runde einer Sitzung: Zeit, gültig ja/nein, Höchsttempo, Spritverbrauch
              und die Messkurven (1000 Punkte pro Kanal), gepackt als komprimiertes JSON

Die .ibt-Datei selbst wird nach dem Auswerten gelöscht. Gespeichert bleibt nur, was das
Labor braucht. Das spart Platz und hält fremde Fahrernamen aus der Datenbank.
"""
# Der Docstring oben wird nicht ausgeführt. Er erklärt die Tabellen.

# json verpackt die Messkurven als Text.
import json

# os liest den Datenbank-Pfad aus der Umgebung (für Tests).
import os

# sqlite3 ist die eingebaute Datenbank von Python.
import sqlite3

# time liefert den Zeitpunkt des Hochladens.
import time

# zlib komprimiert die Messkurven (etwa auf ein Viertel der Größe).
import zlib

# Path baut den Pfad zur Datenbank.
from pathlib import Path

# Datenbank-Datei: labor.db neben diesem Skript, außer LABOR_DB sagt etwas anderes.
DB_DATEI = Path(os.environ.get("LABOR_DB") or Path(__file__).resolve().with_name("labor.db"))

# Bauplan der Tabellen. ON DELETE CASCADE: Löscht man eine Sitzung, verschwinden ihre Runden mit.
SCHEMA = """
CREATE TABLE IF NOT EXISTS sitzung (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hochgeladen REAL NOT NULL,          -- Unix-Zeit des Uploads
    datei       TEXT NOT NULL,          -- ursprünglicher Dateiname
    strecke     TEXT NOT NULL,
    layout      TEXT NOT NULL DEFAULT '',
    laenge_m    INTEGER NOT NULL,       -- Streckenlänge in Metern
    auto        TEXT NOT NULL,
    typ         TEXT NOT NULL,          -- Practice, Race, Time Trial ...
    datum       TEXT NOT NULL           -- wann gefahren wurde
);
CREATE TABLE IF NOT EXISTS runde (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sitzung_id  INTEGER NOT NULL REFERENCES sitzung(id) ON DELETE CASCADE,
    nummer      INTEGER NOT NULL,       -- Rundennummer laut iRacing
    zeit        REAL NOT NULL,          -- Rundenzeit in Sekunden
    gueltig     INTEGER NOT NULL,       -- 1 = saubere Runde
    grund       TEXT NOT NULL,          -- warum ungültig (Box, Ausritt ...)
    vmax        REAL NOT NULL,          -- Höchsttempo in km/h
    sprit       REAL NOT NULL,          -- Verbrauch in Litern
    kanaele     BLOB NOT NULL           -- Messkurven, zlib-komprimiertes JSON
);
CREATE INDEX IF NOT EXISTS runde_sitzung ON runde(sitzung_id);
"""

# Nachkommastellen pro Kanal: genug Genauigkeit, aber kleine Daten.
RUNDEN = {"t": 3, "speed": 1, "gas": 1, "bremse": 1, "gang": 0, "rpm": 0, "lenkung": 1, "lat": 6, "lon": 6}


# Öffnet die Datenbank und legt die Tabellen an, falls sie fehlen.
def verbinden(datei=None):
    con = sqlite3.connect(str(datei or DB_DATEI), timeout=10)
    con.row_factory = sqlite3.Row
    # Fremdschlüssel einschalten (sonst ignoriert SQLite ON DELETE CASCADE).
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(SCHEMA)
    return con


# Packt die Messkurven einer Runde: runden, als JSON schreiben, komprimieren.
def packen(kanaele):
    daten = {k: [round(float(x), RUNDEN[k]) for x in v] for k, v in kanaele.items()}
    return zlib.compress(json.dumps(daten, separators=(",", ":")).encode("utf-8"), 6)


# Gegenstück zu packen().
def entpacken(blob):
    return json.loads(zlib.decompress(blob).decode("utf-8"))


# Speichert eine ausgewertete Datei. Gibt die neue Sitzungs-Nummer zurück.
def speichern(con, session, runden, dateiname):
    with con:
        cur = con.execute(
            "INSERT INTO sitzung (hochgeladen, datei, strecke, layout, laenge_m, auto, typ, datum)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (time.time(), dateiname, session["strecke"], session["layout"], session["laenge_m"],
             session["auto"], session["typ"], session["datum"]))
        sid = cur.lastrowid
        con.executemany(
            "INSERT INTO runde (sitzung_id, nummer, zeit, gueltig, grund, vmax, sprit, kanaele)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(sid, r["nummer"], r["zeit"], int(r["gueltig"]), r["grund"], r["vmax"], r["sprit"], packen(r["kanaele"]))
             for r in runden])
    return sid


# Alle Sitzungen mit Anzahl Runden und bester gültiger Runde, neueste zuerst.
def sitzungen(con):
    return [dict(z) for z in con.execute("""
        SELECT s.id, s.strecke, s.layout, s.laenge_m, s.auto, s.typ, s.datum, s.datei,
               COUNT(r.id) AS runden, SUM(r.gueltig) AS gueltige,
               MIN(CASE WHEN r.gueltig = 1 THEN r.zeit END) AS beste
        FROM sitzung s LEFT JOIN runde r ON r.sitzung_id = s.id
        GROUP BY s.id ORDER BY s.datum DESC, s.id DESC""")]


# Eine Sitzung mit ihren Runden (ohne Messkurven, die kommen einzeln).
def sitzung(con, sid):
    s = con.execute("SELECT * FROM sitzung WHERE id = ?", (sid,)).fetchone()
    if not s:
        return None
    runden = [dict(z) for z in con.execute(
        "SELECT id, nummer, zeit, gueltig, grund, vmax, sprit FROM runde WHERE sitzung_id = ? ORDER BY nummer", (sid,))]
    return dict(s, runden=runden)


# Eine Runde mit Messkurven und den Angaben zur Sitzung (für Karte und Diagramme).
def runde(con, rid):
    z = con.execute("""
        SELECT r.*, s.strecke, s.layout, s.laenge_m, s.auto, s.datum, s.typ
        FROM runde r JOIN sitzung s ON s.id = r.sitzung_id WHERE r.id = ?""", (rid,)).fetchone()
    if not z:
        return None
    daten = dict(z)
    daten["kanaele"] = entpacken(daten["kanaele"])
    return daten


# Bestenliste: schnellste gültige Runde pro Strecke und Auto.
def bestenliste(con):
    return [dict(z) for z in con.execute("""
        SELECT s.strecke, s.auto, MIN(r.zeit) AS zeit, COUNT(r.id) AS runden,
               (SELECT r2.id FROM runde r2 JOIN sitzung s2 ON s2.id = r2.sitzung_id
                 WHERE s2.strecke = s.strecke AND s2.auto = s.auto AND r2.gueltig = 1
                 ORDER BY r2.zeit LIMIT 1) AS runde_id
        FROM runde r JOIN sitzung s ON s.id = r.sitzung_id
        WHERE r.gueltig = 1 GROUP BY s.strecke, s.auto ORDER BY s.strecke, zeit""")]


# Alle gültigen Runden einer Strecke (auch aus anderen Sitzungen und mit anderen Autos), schnellste zuerst.
def runden_der_strecke(con, strecke):
    return [dict(z) for z in con.execute("""
        SELECT r.id, r.nummer, r.zeit, s.auto, s.datum, s.typ, s.id AS sitzung_id
        FROM runde r JOIN sitzung s ON s.id = r.sitzung_id
        WHERE s.strecke = ? AND r.gueltig = 1 ORDER BY r.zeit LIMIT 200""", (strecke,))]


# Zahlen für die Info-Seite: Sitzungen, Runden, gefahrene Kilometer.
def statistik(con):
    z = con.execute("""
        SELECT COUNT(DISTINCT s.id) AS sitzungen, COUNT(r.id) AS runden,
               COALESCE(SUM(s.laenge_m), 0) / 1000.0 AS km
        FROM runde r JOIN sitzung s ON s.id = r.sitzung_id""").fetchone()
    return dict(z)


# Löscht eine Sitzung samt Runden.
def loeschen(con, sid):
    with con:
        return con.execute("DELETE FROM sitzung WHERE id = ?", (sid,)).rowcount > 0
