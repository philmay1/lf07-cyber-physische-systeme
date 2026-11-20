#!/usr/bin/env python3
"""Live-Dashboard der Zutrittskontrolle (Flask).

Start auf dem Pi:  python3 dashboard.py
Aufruf im Browser: http://<IP-des-Pi>:5000  (im Heimnetz oder über Tailscale, auch am Handy)

Zeigt live den Zustand (bereit / gesperrt mit Countdown), die Fehlversuche und das
Protokoll. Ein Admin kann mit seiner PIN die Sperre aus der Ferne aufheben.
Das Dashboard liest dieselbe zutritt.db wie das Keypad-Programm.
Die Webseite selbst steht in dashboard.html.
"""
# Der Docstring oben wird nicht ausgeführt. Er erklärt Start und Zweck.

# os liest Umgebungsvariablen (hier den Port).
import os

# time wandelt Unix-Zeit in Uhrzeit um und kann kurz warten.
import time

# Path findet die Datei dashboard.html im selben Ordner.
from pathlib import Path

# Flask ist ein kleiner Webserver. jsonify macht aus Python-Daten JSON für den Browser,
# request enthält die Daten, die der Browser schickt.
from flask import Flask, jsonify, request

# Unsere Datenbank-Datei zutritt_db.py, hier kurz "db".
import zutritt_db as db

# Die Web-Anwendung anlegen.
app = Flask(__name__)

# Pfad zur Webseite (dashboard.html neben dieser Datei).
SEITE = Path(__file__).with_name("dashboard.html")


# Adresse /api/status: liefert den aktuellen Zustand als JSON. Der Browser fragt das jede Sekunde ab.
# Flask 1.1 auf dem Pi kennt noch kein @app.get, deshalb @app.route.
@app.route("/api/status")
def api_status():
    # Pro Anfrage eine eigene Verbindung öffnen.
    con = db.verbinden()
    # Sperr-Zustand holen (gesperrt, rest, fehlversuche, sperr_stufe).
    s = db.status(con)
    # Die Grenze mitschicken, damit die Seite die richtige Zahl Punkte zeichnet.
    s["max"] = db.MAX_FEHLVERSUCHE
    # Die letzten 12 Versuche als Liste anhängen, jeweils mit lesbarer Uhrzeit.
    s["versuche"] = [{
        "id": v["id"],                                                   # laufende Nummer, erkennt neue Einträge
        "zeit": time.strftime("%H:%M:%S", time.localtime(v["zeit"])),  # z. B. 09:25:45
        "erfolg": bool(v["erfolg"]),                                     # True oder False
        "name": v["name"] or "",                                         # leer bei falscher PIN
        "hinweis": v["hinweis"] or ""} for v in db.letzte_versuche(con, 12)]
    # Vorfall-Nummer: wie oft schon gesperrt wurde.
    s["vorfall"] = db.anzahl_sperren(con)
    # Alles als JSON an den Browser zurückgeben.
    return jsonify(s)


# Adresse /api/entsperren: nimmt eine Admin-PIN entgegen (nur POST, also nicht per Link aufrufbar).
@app.route("/api/entsperren", methods=["POST"])
def api_entsperren():
    # Eigene Datenbank-Verbindung.
    con = db.verbinden()
    # Die PIN aus den JSON-Daten des Browsers lesen. Fehlt sie, wird es ein leerer Text.
    pin = str((request.get_json(silent=True) or {}).get("pin", ""))
    # Nur Ziffern prüfen. Passt die PIN zu einem Benutzer, steht er danach in b.
    b = db.pin_pruefen(con, pin) if pin.isdigit() else None
    # Kein Benutzer oder kein Admin?
    if not b or b["rolle"] != "admin":
        # Den Versuch ins Protokoll schreiben, damit man Angriffe sieht.
        with con:
            con.execute("INSERT INTO versuche (zeit, erfolg, hinweis) VALUES (?, 0, ?)",
                        (time.time(), "Dashboard: falsche Admin-PIN"))
        # 1 Sekunde warten: bremst automatisches Durchprobieren stark aus.
        time.sleep(1)
        # Antwort mit HTTP-Status 403 (verboten).
        return jsonify(ok=False, meldung="Admin-PIN falsch"), 403
    # Admin erkannt: Sperre aufheben und seinen Namen ins Protokoll schreiben.
    db.entsperren(con, f"{b['name']} (Dashboard)")
    # Erfolg melden.
    return jsonify(ok=True, meldung="Entsperrt")


# Startseite /: liefert die Webseite aus dashboard.html.
@app.route("/")
def seite():
    # Datei als Text lesen und an den Browser schicken.
    return SEITE.read_text(encoding="utf-8")


# Nur beim direkten Start den Webserver starten.
if __name__ == "__main__":
    # host="0.0.0.0": erreichbar von anderen Geräten im Netz, nicht nur vom Pi selbst.
    # Port 5000, außer die Umgebungsvariable PORT sagt etwas anderes (für eine Probe parallel).
    # threaded=True: mehrere Browser (Beamer, Handy) gleichzeitig bedienen.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), threaded=True)
