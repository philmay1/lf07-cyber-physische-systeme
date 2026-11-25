#!/usr/bin/env python3
"""Telemetrie-Labor: Web-Server auf dem Pi (Flask, Port 5080).

    python3 labor.py                     Server starten (im Browser: http://<Pi>:5080)
    python3 labor.py passwort            eigenes Passwort für Upload und Löschen setzen
    python3 labor.py import datei.ibt    .ibt direkt auf dem Pi einlesen (ohne Browser)

Ansehen darf jeder im Netz. Hochladen und Löschen nur nach Login.
Ohne gesetztes Passwort sind Hochladen und Löschen nur am Pi selbst erlaubt (localhost).

Einstellungen stehen in .env (Port, maximale Dateigröße), Geheimnisse in .env.password
(Passwort-Hash und Schlüssel für das Login-Cookie). Beide sind per .gitignore gesperrt.
"""
# Der Docstring oben wird nicht ausgeführt. Er dient als Hilfetext.

# getpass liest ein Passwort, ohne es auf dem Bildschirm zu zeigen.
import getpass

# hashlib (PBKDF2) und hmac (sicherer Vergleich) für das Passwort.
import hashlib
import hmac

# os liest Umgebungsvariablen und setzt Dateirechte.
import os

# secrets erzeugt Zufallswerte (Salt, Cookie-Schlüssel).
import secrets

# shutil kopiert den Upload-Datenstrom in eine Datei.
import shutil

# unquote macht aus "%C3%A4" wieder ein "ä" (Dateiname im Kopf der Anfrage).
from urllib.parse import unquote

# sys liest die Befehle (passwort, import).
import sys

# tempfile legt die hochgeladene Datei kurz zwischen.
import tempfile

# Path baut Pfade.
from pathlib import Path

# Flask: Webserver. jsonify macht JSON, request enthält die Anfrage, session das Login-Cookie.
from flask import Flask, jsonify, request, send_from_directory, session

# Ordner dieses Skripts.
HIER = Path(__file__).resolve().parent

# ======== SCHRITT 2 von 21: Der Server startet und liest seine Einstellungen ========
# Port und Größenlimit kommen aus .env, Passwort-Hash und Cookie-Schlüssel aus .env.password. Beides steht nie im Code.
# .env und .env.password laden (python-dotenv). Schon gesetzte Variablen gewinnen.
try:
    from dotenv import load_dotenv
    load_dotenv(HIER / ".env")
    load_dotenv(HIER / ".env.password")
except ImportError:
    pass

# Unsere eigenen Dateien: .ibt lesen und Datenbank.
import ibt_lesen      # noqa: E402
import labor_db       # noqa: E402

# Einstellungen aus .env (mit Standardwerten).
PORT = int(os.environ.get("LABOR_PORT", "5080"))
MAX_MB = int(os.environ.get("LABOR_MAX_MB", "1500"))
# Geheimnisse aus .env.password.
PASSWORT_HASH = os.environ.get("LABOR_PASSWORT_HASH", "")
GEHEIMNIS = os.environ.get("LABOR_GEHEIMNIS", "")

# Die Web-Anwendung. static/ enthält Oberfläche und Diagramm-Bibliothek.
app = Flask(__name__, static_folder="static", static_url_path="/static")
# Schlüssel, mit dem Flask das Login-Cookie unterschreibt. Ohne Eintrag: bei jedem Start neu (Login gilt dann bis zum Neustart).
app.secret_key = GEHEIMNIS or secrets.token_hex(32)
# Größte erlaubte Upload-Datei.
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024


# ---------- Passwort ----------

# ======== SCHRITT 5 von 21: Passwort prüfen, ohne es zu speichern ========
# PBKDF2 rechnet 200.000 Mal SHA-256. Gespeichert wird nur das Ergebnis, das Passwort selbst nie.
# Macht aus einem Passwort einen Hash: pbkdf2$Runden$Salt$Hash (alles als Text).
def hash_bilden(passwort, salt=None, runden=200_000):
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), bytes.fromhex(salt), runden).hex()
    return f"pbkdf2${runden}${salt}${h}"


# Prüft ein Passwort gegen den gespeicherten Hash. compare_digest verrät nichts über die Laufzeit.
def passwort_ok(passwort, gespeichert):
    try:
        _, runden, salt, h = gespeichert.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_bilden(passwort, salt, int(runden)), gespeichert)


# Darf diese Anfrage hochladen oder löschen?
def darf_aendern():
    # Mit Passwort: nur angemeldete Browser.
    if PASSWORT_HASH:
        return bool(session.get("angemeldet"))
    # Ohne Passwort: nur am Pi selbst.
    return request.remote_addr in ("127.0.0.1", "::1")


# Antwort für "nicht erlaubt".
def verboten():
    return jsonify(ok=False, meldung="Bitte erst anmelden."), 401


# ---------- Seiten und Daten ----------

# ======== SCHRITT 3 von 21: Der Browser öffnet die Seite ========
# Flask schickt index.html. Der Browser lädt dann style.css und app.js, und app.js holt alle Daten als JSON.
# Die Oberfläche: eine einzige Seite, der Rest kommt per JavaScript.
@app.route("/")
def start():
    antwort = send_from_directory(HIER / "static", "index.html")
    # no-cache: Der Browser muss vor jeder Nutzung kurz nachfragen, ob sich die Seite geändert hat.
    # Ohne das hält Flask sie 12 Stunden im Zwischenspeicher, und nach einem Update sähe man das alte Design.
    # CSS und JS hängen mit ?v=... an index.html, deshalb reicht es, nur diese eine Datei frisch zu halten.
    antwort.headers["Cache-Control"] = "no-cache"
    return antwort


# Login-Zustand für die Oberfläche.
@app.route("/api/status")
def api_status():
    return jsonify(login_noetig=bool(PASSWORT_HASH), darf_aendern=darf_aendern(), max_mb=MAX_MB)


# Anmelden mit Passwort. Falsche Versuche bremsen wir mit einer Sekunde Wartezeit.
@app.route("/api/login", methods=["POST"])
def api_login():
    passwort = str((request.get_json(silent=True) or {}).get("passwort", ""))
    if PASSWORT_HASH and passwort_ok(passwort, PASSWORT_HASH):
        session["angemeldet"] = True
        return jsonify(ok=True)
    import time
    time.sleep(1)
    return jsonify(ok=False, meldung="Passwort falsch"), 403


# Abmelden: Cookie leeren.
@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify(ok=True)


# ======== SCHRITT 4 von 21: Der Pi meldet, wie es ihm geht ========
# Linux legt Temperatur, Laufzeit und Speicher als kleine Textdateien unter /sys und /proc ab. Wir lesen sie nur.
# Zustand des Pi für die Statusleiste: Temperatur, Last, Speicher, Laufzeit.
# Linux legt diese Werte als Textdateien ab (/sys, /proc). Fehlt eine Datei (z. B. unter Windows), kommt None.
@app.route("/api/system")
def api_system():
    return jsonify(systemwerte())


def systemwerte():
    werte = {"port": PORT}
    # CPU-Temperatur in Tausendstel Grad, z. B. "48312" = 48,3 °C.
    try:
        werte["cpu_temp"] = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    except (OSError, ValueError):
        werte["cpu_temp"] = None
    # Laufzeit seit dem letzten Start in Sekunden (erste Zahl in /proc/uptime).
    try:
        werte["laufzeit_s"] = int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        werte["laufzeit_s"] = None
    # Last: wie viele Prozesse im Schnitt der letzten Minute auf die CPU warten (4 Kerne: unter 4 ist entspannt).
    try:
        werte["last"] = os.getloadavg()[0]
    except (OSError, AttributeError):
        werte["last"] = None
    # Arbeitsspeicher: belegt in Prozent, aus MemTotal und MemAvailable in /proc/meminfo.
    try:
        info = dict(z.split(":", 1) for z in Path("/proc/meminfo").read_text().splitlines() if ":" in z)
        gesamt, frei = int(info["MemTotal"].split()[0]), int(info["MemAvailable"].split()[0])
        werte["ram_prozent"] = round((gesamt - frei) / gesamt * 100)
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        werte["ram_prozent"] = None
    # Größe der Datenbank und freier Platz auf der SD-Karte.
    try:
        werte["db_mb"] = Path(labor_db.DB_DATEI).stat().st_size / 1e6
    except OSError:
        werte["db_mb"] = None
    werte["frei_gb"] = shutil.disk_usage(HIER).free / 1e9
    return werte


# Liste aller Sitzungen.
@app.route("/api/sitzungen")
def api_sitzungen():
    return jsonify(labor_db.sitzungen(labor_db.verbinden()))


# Eine Sitzung mit Runden.
@app.route("/api/sitzung/<int:sid>")
def api_sitzung(sid):
    s = labor_db.sitzung(labor_db.verbinden(), sid)
    return (jsonify(s), 200) if s else (jsonify(meldung="gibt es nicht"), 404)


# Eine Runde mit Messkurven.
@app.route("/api/runde/<int:rid>")
def api_runde(rid):
    r = labor_db.runde(labor_db.verbinden(), rid)
    return (jsonify(r), 200) if r else (jsonify(meldung="gibt es nicht"), 404)


# Gültige Runden einer Strecke, für den Vergleich über Sitzungen und Autos hinweg.
@app.route("/api/runden")
def api_runden():
    return jsonify(labor_db.runden_der_strecke(labor_db.verbinden(), request.args.get("strecke", "")))


# Zahlen für die Info-Seite.
@app.route("/api/statistik")
def api_statistik():
    return jsonify(labor_db.statistik(labor_db.verbinden()))


# Bestenliste pro Strecke und Auto.
@app.route("/api/bestenliste")
def api_bestenliste():
    return jsonify(labor_db.bestenliste(labor_db.verbinden()))


# ======== SCHRITT 7 von 21: Der Server nimmt die Datei an ========
# Erst prüfen, ob dieser Browser das darf. Dann die Datei in eine Zwischendatei schreiben und auswerten lassen.
# .ibt hochladen: zwischenspeichern, auswerten, speichern, Datei löschen.
# Zwei Wege: Der Browser schickt die Datei als reinen Datenstrom (schnell, Name im Kopf X-Dateiname).
# Ein Formular-Upload (z. B. curl -F datei=@...) geht auch, dauert auf dem Pi aber gut doppelt so lange
# (gemessen: 28 MB in 4,6 s statt 2,1 s), weil Flask das Formular in Python zerlegen muss.
@app.route("/api/upload", methods=["POST"])
def api_upload():
    if not darf_aendern():
        return verboten()
    formular = request.files.get("datei")
    # Nur den Dateinamen behalten, nie einen mitgeschickten Pfad.
    name = Path(formular.filename if formular else unquote(request.headers.get("X-Dateiname", ""))).name
    if not name.lower().endswith(".ibt"):
        return jsonify(ok=False, meldung="Bitte eine .ibt-Datei wählen."), 400
    fd, tmp = tempfile.mkstemp(suffix=".ibt")
    os.close(fd)
    try:
        if formular:
            formular.save(tmp)
        else:
            # Datenstrom in 1-MB-Stücken direkt in die Datei schreiben.
            with open(tmp, "wb") as f:
                shutil.copyfileobj(request.stream, f, 1 << 20)
        sid = einlesen(tmp, name)
    except ValueError as fehler:
        return jsonify(ok=False, meldung=f"Datei nicht lesbar: {fehler}"), 400
    # ======== SCHRITT 15 von 21: Die .ibt-Datei wieder löschen ========
    # finally läuft immer, auch nach einem Fehler. So bleibt keine .ibt mit fremden Namen auf dem Pi liegen.
    finally:
        os.remove(tmp)
    return jsonify(ok=True, sitzung=sid)


# Sitzung löschen.
@app.route("/api/sitzung/<int:sid>", methods=["DELETE"])
def api_loeschen(sid):
    if not darf_aendern():
        return verboten()
    return jsonify(ok=labor_db.loeschen(labor_db.verbinden(), sid))


# Zu große Datei: verständliche Meldung statt Fehlerseite.
@app.errorhandler(413)
def zu_gross(_):
    return jsonify(ok=False, meldung=f"Datei größer als {MAX_MB} MB."), 413


# ---------- Hilfen für die Kommandozeile ----------

# Wertet eine .ibt aus und speichert sie. Gibt die Sitzungs-Nummer zurück.
def einlesen(pfad, name):
    session_daten, runden = ibt_lesen.datei_auswerten(pfad)
    if not runden:
        raise ValueError("keine vollständige Runde gefunden")
    return labor_db.speichern(labor_db.verbinden(), session_daten, runden, name)


# Passwort setzen: Hash und Cookie-Schlüssel in .env.password schreiben (Rechte 600).
def passwort_setzen():
    if sys.stdin.isatty():
        p1 = getpass.getpass("Neues Passwort: ")
        p2 = getpass.getpass("Noch einmal: ")
    else:
        p1 = p2 = sys.stdin.readline().rstrip("\n")
    if p1 != p2 or len(p1) < 8:
        sys.exit("Passwörter verschieden oder kürzer als 8 Zeichen.")
    datei = HIER / ".env.password"
    text = ("# Telemetrie-Labor: Geheimnisse. NIE ins Git.\n"
            f"LABOR_PASSWORT_HASH={hash_bilden(p1)}\n"
            f"LABOR_GEHEIMNIS={GEHEIMNIS or secrets.token_hex(32)}\n")
    fd = os.open(datei, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(datei, 0o600)
    print("Passwort gespeichert (.env.password, Rechte 600). Server neu starten.")


# Das Hauptprogramm.
def main():
    befehl = sys.argv[1] if len(sys.argv) > 1 else ""
    if befehl == "passwort":
        passwort_setzen()
    elif befehl == "import":
        for p in sys.argv[2:]:
            try:
                sid = einlesen(p, Path(p).name)
                print(f"{Path(p).name}: Sitzung {sid}")
            except ValueError as fehler:
                print(f"{Path(p).name}: übersprungen ({fehler})")
    elif befehl in ("", "start"):
        print(f"Telemetrie-Labor auf Port {PORT}" + ("" if PASSWORT_HASH else "  (kein Passwort: Upload nur am Pi selbst)"))
        app.run(host="0.0.0.0", port=PORT, threaded=True)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
