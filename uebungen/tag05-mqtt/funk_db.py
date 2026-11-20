"""Gemeinsame Bausteine für SENTINEL Funk: Datenbank mqtt.db und MQTT-Client.

Die Tabelle events speichert jedes MQTT-Event mit Zeit, Topic, Sender und Wert.
Logger, Brücke und Web-Board nutzen diese Datei, damit alle dieselbe Datenbank lesen.
"""
# Der Docstring oben wird nicht ausgeführt. Er erklärt, wofür die Datei da ist.

# json liest Nachrichten im Format {"wert": ..., "sender": ...}.
import json

# os liest Umgebungsvariablen (eigener Datenbank-Pfad für Tests).
import os

# random hängt eine Zufallszahl an den Client-Namen, damit jeder Client eindeutig ist.
import random

# sqlite3 ist die eingebaute Datenbank von Python. Eine Datei, kein Server.
import sqlite3

# time liefert die aktuelle Zeit als Sekunden seit 1970 (Unix-Zeit).
import time

# Path baut Dateipfade, die unter Windows und Linux funktionieren.
from pathlib import Path

# paho-mqtt ist die MQTT-Bibliothek für Python.
import paho.mqtt.client as mqtt

# Datenbank-Datei: mqtt.db neben diesem Skript, außer FUNK_DB sagt etwas anderes.
DB_DATEI = Path(os.environ.get("FUNK_DB") or Path(__file__).with_name("mqtt.db"))

# Adresse des Brokers. Auf dem Pi läuft Mosquitto selbst, also "localhost".
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")

# Alles, was mit lf07/ anfängt, gehört zu unserer Übung. # heißt: alle Unter-Topics.
THEMA = "lf07/#"

# Bauplan der Tabelle. IF NOT EXISTS: nur anlegen, wenn sie noch fehlt.
SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,  -- laufende Nummer, vergibt SQLite selbst
    zeit   REAL    NOT NULL,                   -- Empfangszeit in Sekunden seit 1970
    topic  TEXT    NOT NULL,                   -- z. B. lf07/handy/lisa/knopf
    sender TEXT    NOT NULL DEFAULT '',        -- wer gesendet hat
    wert   TEXT    NOT NULL                    -- der gesendete Wert als Text
);
"""


# Öffnet die Datenbank und legt die Tabelle an, falls sie fehlt.
def verbinden(datei=None):
    # Verbindung öffnen. timeout=5: bis zu 5 s warten, wenn gerade ein anderes Programm schreibt.
    con = sqlite3.connect(str(datei or DB_DATEI), timeout=5)
    # Zeilen sollen sich wie ein Wörterbuch lesen lassen: zeile["topic"].
    con.row_factory = sqlite3.Row
    # WAL-Modus: Lesen und Schreiben gleichzeitig (Logger schreibt, Board liest).
    con.execute("PRAGMA journal_mode=WAL")
    # Tabelle anlegen (passiert nur beim ersten Mal).
    con.executescript(SCHEMA)
    # Die fertige Verbindung zurückgeben.
    return con


# Macht aus den rohen Bytes einer MQTT-Nachricht einen Wert und einen Sender.
def payload_lesen(topic, payload):
    # Bytes in Text umwandeln. errors="replace": kaputte Zeichen werden zu ?, statt abzustürzen.
    text = payload.decode("utf-8", errors="replace").strip()
    # Ohne JSON ist der Sender der zweite Teil des Topics (lf07/<sender>/...).
    teile = topic.split("/")
    sender = teile[1] if len(teile) > 1 else ""
    # Versuchen, den Text als JSON zu lesen.
    try:
        daten = json.loads(text)
    # Kein gültiges JSON? Dann ist der ganze Text der Wert.
    except ValueError:
        daten = None
    # War es ein JSON-Objekt mit "wert"? Dann Wert und Sender daraus nehmen.
    if isinstance(daten, dict) and "wert" in daten:
        text = str(daten["wert"])
        sender = str(daten.get("sender") or sender)
    # PINs nie im Klartext speichern: nur zeigen, wie viele Stellen es waren.
    if topic.endswith("/pin"):
        text = "PIN " + "*" * min(len(text), 8)
    # Sehr lange Werte kürzen, damit niemand die Datenbank vollschreibt.
    return text[:200], sender[:40]


# Speichert ein Event und gibt seine neue Nummer (id) zurück.
def event_speichern(con, topic, wert, sender="", zeit=None):
    # with con: speichert am Ende automatisch (commit), bei einem Fehler wird alles zurückgenommen.
    with con:
        # Platzhalter ? schützen vor SQL-Injection: die Werte werden nie in den SQL-Text geklebt.
        cur = con.execute("INSERT INTO events (zeit, topic, sender, wert) VALUES (?, ?, ?, ?)",
                          (zeit or time.time(), topic, sender, wert))
    # Die id, die SQLite gerade vergeben hat.
    return cur.lastrowid


# Holt die neuesten Events, das neueste zuerst.
def letzte_events(con, anzahl=10):
    # datetime(..., 'unixepoch', 'localtime') macht aus Sekunden eine lesbare Uhrzeit.
    return con.execute(
        "SELECT id, zeit, strftime('%H:%M:%S', zeit, 'unixepoch', 'localtime') AS uhrzeit,"
        " topic, sender, wert FROM events ORDER BY id DESC LIMIT ?", (anzahl,)).fetchall()


# Zählt alle Events in der Tabelle.
def anzahl(con):
    # COUNT(*) zählt Zeilen. [0] nimmt die eine Zahl aus dem Ergebnis.
    return con.execute("SELECT COUNT(*) FROM events").fetchone()[0]


# Löscht alle Events (für eine frische Vorführung).
def leeren(con):
    # Inhalt löschen und den id-Zähler auf 0 setzen.
    with con:
        con.execute("DELETE FROM events")
        con.execute("DELETE FROM sqlite_sequence WHERE name = 'events'")


# Baut einen MQTT-Client, der mit paho-mqtt 1.x (Pi) und 2.x (Notebook) läuft.
def client_bauen(name):
    # Eindeutiger Name, z. B. "logger-4821". Zwei Clients mit gleichem Namen werfen sich gegenseitig raus.
    client_id = f"{name}-{random.randint(1000, 9999)}"
    # paho 2.x will wissen, welche Form die Rückruf-Funktionen haben.
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    # paho 1.x kennt CallbackAPIVersion noch nicht.
    except AttributeError:
        return mqtt.Client(client_id=client_id)
