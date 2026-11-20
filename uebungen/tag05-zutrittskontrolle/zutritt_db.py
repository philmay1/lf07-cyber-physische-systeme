"""Datenbank der Zutrittskontrolle (SQLite).

Hier steht alles, was mit der Datei zutritt.db zu tun hat:
Benutzer mit PIN-Hash, Protokoll aller Versuche und die Sperre.
Die Sperre liegt bewusst in der Datenbank und nicht nur im Arbeitsspeicher.
So hebt ein Neustart oder Stecker ziehen die Sperre nicht auf.
"""
import hashlib
import hmac
import os
import sqlite3
import time
from pathlib import Path

DB_DATEI = Path(__file__).with_name("zutritt.db")
MAX_FEHLVERSUCHE = 3          # nach so vielen Fehlern wird gesperrt
SPERRE_START = 60             # erste Sperre in Sekunden, danach doppelt so lang
SPERRE_MAX = 15 * 60          # längste Sperre: 15 Minuten
HASH_RUNDEN = 100_000         # PBKDF2-Runden: macht Durchprobieren langsam

SCHEMA = """
CREATE TABLE IF NOT EXISTS benutzer (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL UNIQUE,
    salt      BLOB NOT NULL,
    pin_hash  BLOB NOT NULL,
    rolle     TEXT NOT NULL DEFAULT 'nutzer' CHECK (rolle IN ('nutzer', 'admin')),
    aktiv     INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS versuche (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    zeit        REAL NOT NULL,
    erfolg      INTEGER NOT NULL,
    benutzer_id INTEGER REFERENCES benutzer(id),
    hinweis     TEXT
);
CREATE TABLE IF NOT EXISTS sperre (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    fehlversuche  INTEGER NOT NULL DEFAULT 0,
    sperr_stufe   INTEGER NOT NULL DEFAULT 0,
    gesperrt_bis  REAL NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO sperre (id) VALUES (1);
"""


def verbinden(datei=None):
    """Öffnet die Datenbank. WAL erlaubt, dass Keypad und Dashboard gleichzeitig zugreifen."""
    con = sqlite3.connect(str(datei or DB_DATEI), timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA)
    return con


def pin_hashen(pin, salt=None):
    """PIN nie im Klartext speichern: Salt + PBKDF2-SHA256."""
    salt = salt or os.urandom(16)
    return salt, hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, HASH_RUNDEN)


def benutzer_anlegen(con, name, pin, rolle="nutzer"):
    if not (pin.isdigit() and 4 <= len(pin) <= 8):
        raise ValueError("PIN muss aus 4 bis 8 Ziffern bestehen")
    salt, h = pin_hashen(pin)
    with con:
        con.execute("INSERT INTO benutzer (name, salt, pin_hash, rolle) VALUES (?, ?, ?, ?)",
                    (name, salt, h, rolle))


def pin_pruefen(con, pin):
    """Gibt den passenden Benutzer zurück oder None. Vergleich in konstanter Zeit."""
    for b in con.execute("SELECT * FROM benutzer WHERE aktiv = 1"):
        _, h = pin_hashen(pin, b["salt"])
        if hmac.compare_digest(h, b["pin_hash"]):
            return b
    return None


def status(con, jetzt=None):
    jetzt = jetzt or time.time()
    s = con.execute("SELECT * FROM sperre WHERE id = 1").fetchone()
    rest = max(0, s["gesperrt_bis"] - jetzt)
    return {"gesperrt": rest > 0, "rest": rest, "fehlversuche": s["fehlversuche"],
            "sperr_stufe": s["sperr_stufe"]}


def versuch_eintragen(con, erfolg, benutzer=None, hinweis="", jetzt=None):
    """Schreibt den Versuch ins Protokoll und pflegt Zähler und Sperre.

    Rückgabe: "ok", "falsch" oder "gesperrt" (dieser Fehler hat die Sperre ausgelöst).
    """
    jetzt = jetzt or time.time()
    with con:
        con.execute("INSERT INTO versuche (zeit, erfolg, benutzer_id, hinweis) VALUES (?, ?, ?, ?)",
                    (jetzt, int(erfolg), benutzer["id"] if benutzer else None, hinweis))
        if erfolg:
            con.execute("UPDATE sperre SET fehlversuche = 0, sperr_stufe = 0 WHERE id = 1")
            return "ok"
        s = con.execute("SELECT * FROM sperre WHERE id = 1").fetchone()
        fehler = s["fehlversuche"] + 1
        if fehler < MAX_FEHLVERSUCHE:
            con.execute("UPDATE sperre SET fehlversuche = ? WHERE id = 1", (fehler,))
            return "falsch"
        dauer = min(SPERRE_START * 2 ** s["sperr_stufe"], SPERRE_MAX)
        con.execute("UPDATE sperre SET fehlversuche = 0, sperr_stufe = sperr_stufe + 1,"
                    " gesperrt_bis = ? WHERE id = 1", (jetzt + dauer,))
        con.execute("INSERT INTO versuche (zeit, erfolg, hinweis) VALUES (?, 0, ?)",
                    (jetzt, f"GESPERRT für {dauer} s"))
        return "gesperrt"


def entsperren(con, wer="admin"):
    with con:
        con.execute("UPDATE sperre SET fehlversuche = 0, sperr_stufe = 0, gesperrt_bis = 0 WHERE id = 1")
        con.execute("INSERT INTO versuche (zeit, erfolg, hinweis) VALUES (?, 1, ?)",
                    (time.time(), f"entsperrt durch {wer}"))


def letzte_versuche(con, anzahl=15):
    return con.execute("""SELECT v.zeit, v.erfolg, v.hinweis, b.name FROM versuche v
                          LEFT JOIN benutzer b ON b.id = v.benutzer_id
                          ORDER BY v.id DESC LIMIT ?""", (anzahl,)).fetchall()
