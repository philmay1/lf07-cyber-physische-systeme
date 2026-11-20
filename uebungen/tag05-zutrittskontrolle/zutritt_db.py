"""Datenbank der Zutrittskontrolle (SQLite).

Hier steht alles, was mit der Datei zutritt.db zu tun hat:
Benutzer mit PIN-Hash, Protokoll aller Versuche und die Sperre.
Die Sperre liegt bewusst in der Datenbank und nicht nur im Arbeitsspeicher.
So hebt ein Neustart oder Stecker ziehen die Sperre nicht auf.
"""
# Der Docstring oben wird nicht ausgeführt. Er beschreibt, wofür die Datei da ist.

# hashlib berechnet Hashes. Aus der PIN wird damit ein unlesbarer "Fingerabdruck".
import hashlib

# hmac bringt compare_digest: vergleicht zwei Hashes immer gleich schnell,
# damit ein Angreifer nicht an der Antwortzeit ablesen kann, wie viel schon stimmt.
import hmac

# os liefert os.urandom: echte Zufallsbytes für das Salt.
import os

# sqlite3 ist die Datenbank. Sie steckt schon in Python, installieren muss man nichts.
import sqlite3

# time liefert die aktuelle Uhrzeit als Sekunden seit 1970 (Unix-Zeit).
import time

# Path baut Dateipfade, die unter Windows und Linux gleich funktionieren.
from pathlib import Path

# Die Datenbank-Datei liegt im selben Ordner wie dieses Skript und heißt zutritt.db.
DB_DATEI = Path(__file__).with_name("zutritt.db")

# Nach so vielen falschen PINs hintereinander wird gesperrt.
MAX_FEHLVERSUCHE = 3

# Die erste Sperre dauert 60 Sekunden. Jede weitere dauert doppelt so lang.
SPERRE_START = 60

# Länger als 15 Minuten (15 * 60 Sekunden) wird nie gesperrt.
SPERRE_MAX = 15 * 60

# So oft wird beim Hashen gerechnet. Das macht Durchprobieren aller PINs langsam.
HASH_RUNDEN = 100_000

# SCHEMA ist der Bauplan der Datenbank in der Sprache SQL.
# "IF NOT EXISTS" heißt: Tabelle nur anlegen, wenn es sie noch nicht gibt.
SCHEMA = """
-- Tabelle 1: wer darf rein
CREATE TABLE IF NOT EXISTS benutzer (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,  -- laufende Nummer, vergibt SQLite selbst
    name      TEXT NOT NULL UNIQUE,               -- Name, jeder nur einmal
    salt      BLOB NOT NULL,                      -- Zufallsbytes, für jeden Benutzer anders
    pin_hash  BLOB NOT NULL,                      -- Hash aus PIN und Salt, nie die PIN selbst
    rolle     TEXT NOT NULL DEFAULT 'nutzer'      -- 'nutzer' oder 'admin'
              CHECK (rolle IN ('nutzer', 'admin')),
    aktiv     INTEGER NOT NULL DEFAULT 1          -- 1 = darf rein, 0 = gesperrter Benutzer
);
-- Tabelle 2: Protokoll, jeder Versuch eine Zeile
CREATE TABLE IF NOT EXISTS versuche (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,  -- laufende Nummer
    zeit        REAL NOT NULL,                      -- Zeitpunkt als Unix-Zeit
    erfolg      INTEGER NOT NULL,                   -- 1 = richtig, 0 = falsch
    benutzer_id INTEGER REFERENCES benutzer(id),    -- wer es war (leer bei falscher PIN)
    hinweis     TEXT                                -- Zusatztext, z. B. "GESPERRT für 60 s"
);
-- Tabelle 3: der Sperr-Zustand, immer genau eine Zeile mit id 1
CREATE TABLE IF NOT EXISTS sperre (
    id            INTEGER PRIMARY KEY CHECK (id = 1),  -- es darf nur Zeile 1 geben
    fehlversuche  INTEGER NOT NULL DEFAULT 0,          -- Fehler seit der letzten richtigen PIN
    sperr_stufe   INTEGER NOT NULL DEFAULT 0,          -- wie oft schon gesperrt wurde
    gesperrt_bis  REAL NOT NULL DEFAULT 0              -- bis wann gesperrt ist (Unix-Zeit)
);
-- Zeile 1 anlegen, falls sie fehlt. OR IGNORE: gibt es sie schon, passiert nichts.
INSERT OR IGNORE INTO sperre (id) VALUES (1);
"""


# Öffnet die Datenbank und gibt die Verbindung zurück.
def verbinden(datei=None):
    # Verbindung zur Datei herstellen. timeout=5: bis zu 5 s warten, falls gerade jemand schreibt.
    con = sqlite3.connect(str(datei or DB_DATEI), timeout=5)
    # Zeilen sollen sich wie ein Wörterbuch lesen lassen: zeile["name"] statt zeile[1].
    con.row_factory = sqlite3.Row
    # WAL-Modus: Keypad-Programm und Dashboard dürfen gleichzeitig auf die Datei zugreifen.
    con.execute("PRAGMA journal_mode=WAL")
    # Fremdschlüssel prüfen lassen: benutzer_id muss es in der Tabelle benutzer wirklich geben.
    con.execute("PRAGMA foreign_keys=ON")
    # Den Bauplan von oben ausführen. Beim ersten Start entstehen so die Tabellen.
    con.executescript(SCHEMA)
    # Die fertige Verbindung an den Aufrufer zurückgeben.
    return con


# Macht aus einer PIN einen Hash. Ohne salt wird ein neues zufälliges Salt erzeugt.
def pin_hashen(pin, salt=None):
    # Gibt es noch kein Salt (neuer Benutzer), 16 Zufallsbytes erzeugen.
    salt = salt or os.urandom(16)
    # PBKDF2 mit SHA-256: PIN und Salt werden 100.000-mal durch den Hash gejagt.
    # Rückgabe: das Salt und der Hash, beides wird gespeichert.
    return salt, hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, HASH_RUNDEN)


# Legt einen neuen Benutzer an.
def benutzer_anlegen(con, name, pin, rolle="nutzer"):
    # Die PIN muss nur aus Ziffern bestehen und 4 bis 8 Stellen lang sein.
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        # Sonst abbrechen mit einer verständlichen Fehlermeldung.
        raise ValueError("PIN muss aus 4 bis 8 Ziffern bestehen")
    # Salt und Hash für diese PIN berechnen.
    salt, h = pin_hashen(pin)
    # "with con" speichert am Ende automatisch (commit) oder macht bei Fehlern alles rückgängig.
    with con:
        # Neue Zeile in die Tabelle benutzer schreiben. Die ? werden sicher mit den Werten gefüllt
        # (Schutz gegen SQL-Injection, falls jemand einen bösen Namen eingibt).
        con.execute("INSERT INTO benutzer (name, salt, pin_hash, rolle) VALUES (?, ?, ?, ?)",
                    (name, salt, h, rolle))


# Sucht den Benutzer zur eingegebenen PIN. Rückgabe: der Benutzer oder None.
def pin_pruefen(con, pin):
    # Alle aktiven Benutzer der Reihe nach durchgehen.
    for b in con.execute("SELECT * FROM benutzer WHERE aktiv = 1"):
        # Die eingegebene PIN mit dem Salt dieses Benutzers hashen.
        _, h = pin_hashen(pin, b["salt"])
        # Stimmt der neue Hash mit dem gespeicherten überein, ist es dieser Benutzer.
        if hmac.compare_digest(h, b["pin_hash"]):
            # Treffer: Benutzer zurückgeben.
            return b
    # Kein Benutzer passt: falsche PIN.
    return None


# Liefert den aktuellen Sperr-Zustand als Wörterbuch.
def status(con, jetzt=None):
    # Aktuelle Zeit nehmen, falls keine mitgegeben wurde (Tests geben eine eigene Zeit mit).
    jetzt = jetzt or time.time()
    # Die eine Zeile aus der Tabelle sperre lesen.
    s = con.execute("SELECT * FROM sperre WHERE id = 1").fetchone()
    # Restliche Sperrzeit in Sekunden. max(0, ...) verhindert negative Werte.
    rest = max(0, s["gesperrt_bis"] - jetzt)
    # Alles Wichtige zusammenpacken: gesperrt ja/nein, Restzeit, Fehlerzahl, Stufe.
    return {"gesperrt": rest > 0, "rest": rest, "fehlversuche": s["fehlversuche"],
            "sperr_stufe": s["sperr_stufe"]}


# Schreibt einen Versuch ins Protokoll und zählt Fehler. Rückgabe: "ok", "falsch" oder "gesperrt".
def versuch_eintragen(con, erfolg, benutzer=None, hinweis="", jetzt=None):
    # Aktuelle Zeit nehmen, falls keine mitgegeben wurde.
    jetzt = jetzt or time.time()
    # Alles in einem Rutsch speichern oder gar nicht (Transaktion).
    with con:
        # Den Versuch ins Protokoll schreiben. Bei falscher PIN bleibt benutzer_id leer (None).
        con.execute("INSERT INTO versuche (zeit, erfolg, benutzer_id, hinweis) VALUES (?, ?, ?, ?)",
                    (jetzt, int(erfolg), benutzer["id"] if benutzer else None, hinweis))
        # Richtige PIN?
        if erfolg:
            # Dann Fehlerzähler und Sperrstufe auf 0 zurücksetzen.
            con.execute("UPDATE sperre SET fehlversuche = 0, sperr_stufe = 0 WHERE id = 1")
            # Ergebnis melden: Tür darf auf.
            return "ok"
        # Falsche PIN: aktuellen Sperr-Zustand lesen.
        s = con.execute("SELECT * FROM sperre WHERE id = 1").fetchone()
        # Fehlerzähler um eins erhöhen.
        fehler = s["fehlversuche"] + 1
        # Noch unter der Grenze (also Fehler 1 oder 2)?
        if fehler < MAX_FEHLVERSUCHE:
            # Neuen Zählerstand speichern.
            con.execute("UPDATE sperre SET fehlversuche = ? WHERE id = 1", (fehler,))
            # Ergebnis melden: falsch, aber noch nicht gesperrt.
            return "falsch"
        # Dritter Fehler: Sperrdauer ausrechnen. Stufe 0 = 60 s, 1 = 120 s, 2 = 240 s ...
        # min(...) begrenzt das auf höchstens 15 Minuten.
        dauer = min(SPERRE_START * 2 ** s["sperr_stufe"], SPERRE_MAX)
        # Zähler zurück auf 0, Stufe eins höher, Sperrende = jetzt + Dauer.
        con.execute("UPDATE sperre SET fehlversuche = 0, sperr_stufe = sperr_stufe + 1,"
                    " gesperrt_bis = ? WHERE id = 1", (jetzt + dauer,))
        # Die Sperre selbst auch ins Protokoll schreiben, damit man sie später sieht.
        con.execute("INSERT INTO versuche (zeit, erfolg, hinweis) VALUES (?, 0, ?)",
                    (jetzt, f"GESPERRT für {dauer} s"))
        # Ergebnis melden: dieser Fehler hat die Sperre ausgelöst.
        return "gesperrt"


# Hebt die Sperre sofort auf (Admin im Dashboard oder verwalten.py).
def entsperren(con, wer="admin"):
    # Speichern als eine Transaktion.
    with con:
        # Zähler, Stufe und Sperrende zurücksetzen.
        con.execute("UPDATE sperre SET fehlversuche = 0, sperr_stufe = 0, gesperrt_bis = 0 WHERE id = 1")
        # Ins Protokoll schreiben, wer entsperrt hat.
        con.execute("INSERT INTO versuche (zeit, erfolg, hinweis) VALUES (?, 1, ?)",
                    (time.time(), f"entsperrt durch {wer}"))


# Liefert die neuesten Protokoll-Einträge, der jüngste zuerst.
def letzte_versuche(con, anzahl=15):
    # LEFT JOIN holt den Benutzernamen dazu. Bei falscher PIN gibt es keinen, dann bleibt name leer.
    # ORDER BY v.id DESC sortiert absteigend, LIMIT begrenzt die Anzahl.
    return con.execute("""SELECT v.zeit, v.erfolg, v.hinweis, b.name FROM versuche v
                          LEFT JOIN benutzer b ON b.id = v.benutzer_id
                          ORDER BY v.id DESC LIMIT ?""", (anzahl,)).fetchall()
