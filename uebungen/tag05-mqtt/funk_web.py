#!/usr/bin/env python3
"""Web-Teil von SENTINEL Funk (Flask, Port 5050).

    /          Live-Board für den Beamer: Pakete fliegen Sender -> Mosquitto -> Datenbank
    /handy     Seite für die Handys der Klasse (QR-Code auf dem Board)
    /api/...   Daten aus mqtt.db für das Board

Die Handys und das Board sprechen selbst MQTT (über WebSocket, Port 9001).
Flask liefert nur die Seiten aus und liest die Datenbank.

Start auf dem Pi:  python3 funk_web.py
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er erklärt Zweck und Start.

# io baut eine Datei im Arbeitsspeicher (für das QR-Bild).
import io

# json schreibt die Zugangsdaten für den Browser in die Seite.
import json

# os liest Umgebungsvariablen (Port, eigene Adresse).
import os

# socket findet die IP-Adresse des Pi im Netz.
import socket

# Path findet die HTML-Dateien neben diesem Skript.
from pathlib import Path

# Flask ist der kleine Webserver. jsonify macht JSON, Response schickt das QR-Bild.
from flask import Flask, Response, jsonify

# Unsere gemeinsame Datenbank-Datei.
import funk_db as fdb

# Die Web-Anwendung anlegen. Dateien in static/ (mqtt.min.js) liefert Flask automatisch aus.
app = Flask(__name__)

# Ordner dieses Skripts, dort liegen board.html und handy.html.
ORDNER = Path(__file__).resolve().parent

# Port der Webseite. 5000 ist schon vom SENTINEL-Dashboard belegt.
PORT = int(os.environ.get("FUNK_PORT") or os.environ.get("PORT") or 5050)

# Port für MQTT über WebSocket (Browser), Standard 9001.
WS_PORT = int(os.environ.get("MQTT_WS_PORT", "9001"))


# Findet die IP-Adresse, unter der Handys im selben WLAN den Pi erreichen.
def eigene_ip():
    # Wer die Adresse kennt (z. B. hinter einem Router), kann sie per FUNK_IP vorgeben.
    if os.environ.get("FUNK_IP"):
        return os.environ["FUNK_IP"]
    # Trick: Ein UDP-"Anruf" nach außen verrät, welche eigene Adresse benutzt wird.
    # Dabei wird kein einziges Paket verschickt.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    # Ohne Netz: wenigstens localhost.
    except OSError:
        return "127.0.0.1"
    # Den Socket in jedem Fall schließen.
    finally:
        s.close()


# Adresse der Handyseite, die im QR-Code steckt.
def handy_url():
    return f"http://{eigene_ip()}:{PORT}/handy"


# Liest eine HTML-Seite und setzt die MQTT-Verbindungsdaten für die passende Rolle ein.
# Wichtig: Alles, was im Browser landet, kann jeder Besucher sehen. Deshalb bekommen Board und
# Handy nur Rollen mit wenig Rechten (siehe funk_sicherheit.py): Das Board darf nur lesen und sieht
# keine PINs, das Handy darf nur Knöpfe und PINs senden. Andere Passwörter verlassen den Pi nie.
def seite_mit_zugang(datei, rolle):
    # Daten für mqtt.js: WebSocket-Port und, falls vorhanden, Benutzer und Passwort.
    daten = {"port": WS_PORT}
    login = fdb.zugang(rolle)
    if login:
        daten.update(username=login[0], password=login[1])
    # Platzhalter __ZUGANG__ in der Seite durch JSON ersetzen.
    return (ORDNER / datei).read_text(encoding="utf-8").replace("__ZUGANG__", json.dumps(daten))


# Startseite: das Live-Board (Rolle board).
@app.route("/")
def board():
    return seite_mit_zugang("board.html", "board")


# Die Seite für die Handys (Rolle handy).
@app.route("/handy")
def handy():
    return seite_mit_zugang("handy.html", "handy")


# Die neuesten Events und die Gesamtzahl aus der Datenbank.
@app.route("/api/events")
def api_events():
    # Pro Anfrage eine eigene Verbindung (Flask bedient mehrere Browser gleichzeitig).
    con = fdb.verbinden()
    # Die letzten 10 Zeilen als Liste von Wörterbüchern.
    zeilen = [dict(z) for z in fdb.letzte_events(con, 10)]
    # Gesamtzahl dazu, dann als JSON zurück.
    return jsonify(anzahl=fdb.anzahl(con), events=zeilen)


# Infos für das Board: Adresse der Handyseite.
@app.route("/api/info")
def api_info():
    return jsonify(handy_url=handy_url())


# Der QR-Code mit der Adresse der Handyseite als SVG-Bild.
@app.route("/qr.svg")
def qr():
    # qrcode ist eine Zusatz-Bibliothek (Pi: sudo apt install python3-qrcode).
    try:
        import qrcode
        import qrcode.image.svg
    # Fehlt sie, gibt es eben keinen QR-Code. Das Board zeigt dann nur die Adresse.
    except ImportError:
        return Response("qrcode fehlt", status=404)
    # QR-Code als SVG (Vektorbild, bleibt am Beamer scharf) erzeugen.
    bild = qrcode.make(handy_url(), image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    # In eine Datei im Arbeitsspeicher schreiben ...
    puffer = io.BytesIO()
    bild.save(puffer)
    # ... und als SVG an den Browser schicken.
    return Response(puffer.getvalue(), mimetype="image/svg+xml")


# Nur beim direkten Start den Webserver starten.
if __name__ == "__main__":
    print("Board:", f"http://localhost:{PORT}", " Handys:", handy_url())
    # 0.0.0.0: aus dem ganzen Netz erreichbar. threaded=True: viele Handys gleichzeitig.
    app.run(host="0.0.0.0", port=PORT, threaded=True)
