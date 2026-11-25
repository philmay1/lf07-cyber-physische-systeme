#!/usr/bin/env python3
"""Absicherung von SENTINEL Funk: Rollen, Schlüssel und Broker-Einstellungen (Tag 8).

    python3 funk_sicherheit.py schluessel           .env und .env.password anlegen (zufällige Passwörter)
    sudo python3 funk_sicherheit.py broker          Mosquitto auf Login und Rechte (ACL) umstellen
    sudo python3 funk_sicherheit.py offen           zurück zum offenen Broker ohne Login (wie Tag 5)
    python3 funk_sicherheit.py notebook <ordner>    Zugang fürs Notebook: nur das Sender-Passwort
    python3 funk_sicherheit.py rechte               zeigt, welche Rolle was darf

Aufteilung der Dateien:
    .env            Einstellungen ohne Geheimnisse (Host, Ports). Nicht im Git, weil rechnerabhängig.
    .env.password   nur die Passwörter, eine Zeile pro Rolle. Nicht im Git, Rechte 600.
    .env.example    Vorlage mit Platzhaltern. Die liegt im Git.
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er dient als Hilfetext (-h).

# argparse liest die Unterbefehle (schluessel, broker, ...).
import argparse

# os setzt Dateirechte und prüft, ob wir root sind.
import os

# secrets erzeugt kryptografisch sichere Zufallspasswörter (random ist dafür NICHT geeignet).
import secrets

# subprocess startet mosquitto_passwd und systemctl.
import subprocess

# sys beendet das Programm mit einer Meldung.
import sys

# Path baut die Dateipfade.
from pathlib import Path

# Ordner dieses Skripts. Dort liegen .env und .env.password.
HIER = Path(__file__).resolve().parent
# Einstellungen ohne Geheimnisse.
ENV_DATEI = HIER / ".env"
# Nur die Passwörter.
PASSWORT_DATEI = HIER / ".env.password"

# Dateien von Mosquitto auf dem Pi.
MOSQ_PASSWD = Path("/etc/mosquitto/lf07_passwd")      # Benutzer mit Passwort-Hash
MOSQ_ACL = Path("/etc/mosquitto/lf07_acl")            # wer welches Topic lesen oder schreiben darf
MOSQ_CONF = Path("/etc/mosquitto/conf.d/lf07.conf")   # unsere Broker-Einstellung

# Jede Rolle ist ein eigener MQTT-Benutzer mit genau den Rechten, die sie braucht.
# read = Topic abonnieren und empfangen, write = auf das Topic senden. Alles andere ist verboten.
ROLLEN = {
    "logger":  ("schreibt alle Events in mqtt.db",       ["read lf07/#"]),
    "board":   ("Live-Board am Beamer, nur lesen",        ["read lf07/handy/#", "read lf07/sender/#",
                                                           "read lf07/keypad/#", "read lf07/zutritt/antwort/#"]),
    "bruecke": ("prüft PINs, antwortet dem Handy",        ["read lf07/zutritt/pin", "write lf07/zutritt/antwort/#"]),
    "keypad":  ("zutritt.py meldet PIN-Ergebnisse",       ["write lf07/keypad/versuch"]),
    "sender":  ("sender.py auf Pi und Notebook",          ["write lf07/sender/#"]),
    "handy":   ("Handyseite der Klasse",                  ["write lf07/handy/#", "write lf07/zutritt/pin",
                                                           "read lf07/zutritt/antwort/#"]),
}

# Inhalt einer neuen .env (keine Geheimnisse, nur Einstellungen).
ENV_VORLAGE = """# SENTINEL Funk: Einstellungen für diesen Rechner (keine Passwörter!)
# Nicht ins Git, weil die Werte auf jedem Rechner anders sind. Vorlage: .env.example
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_WS_PORT=9001
FUNK_PORT=5050
"""


# Liest eine .env-Datei in ein Wörterbuch. Bewusst ohne Zusatzpaket, damit das Einrichten immer klappt.
def env_lesen(pfad):
    werte = {}
    # Fehlt die Datei, gibt es eben ein leeres Wörterbuch.
    if not pfad.exists():
        return werte
    # Zeile für Zeile lesen.
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        # Leere Zeilen und Kommentare überspringen.
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        # Am ersten = teilen: links der Name, rechts der Wert.
        name, wert = zeile.split("=", 1)
        # Anführungszeichen um den Wert entfernen.
        werte[name.strip()] = wert.strip().strip('"').strip("'")
    return werte


# Schreibt eine Datei, die von Anfang an nur der Besitzer lesen darf (Rechte 600).
def geheim_schreiben(pfad, text):
    # os.open mit Modus 0o600 legt die Datei gleich mit den richtigen Rechten an.
    # So gibt es keinen Moment, in dem andere Benutzer sie lesen könnten.
    fd = os.open(pfad, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    # Falls die Datei schon da war, die Rechte trotzdem auf 600 setzen.
    os.chmod(pfad, 0o600)


# Unterbefehl "schluessel": legt .env und .env.password an.
def schluessel():
    # .env nur anlegen, wenn sie fehlt. Eigene Änderungen bleiben erhalten.
    if ENV_DATEI.exists():
        print(f"{ENV_DATEI.name} gibt es schon, bleibt wie sie ist.")
    else:
        ENV_DATEI.write_text(ENV_VORLAGE, encoding="utf-8")
        print(f"{ENV_DATEI.name} angelegt.")
    # Vorhandene Passwörter nie überschreiben, sonst passen sie nicht mehr zum Broker.
    if PASSWORT_DATEI.exists():
        print(f"{PASSWORT_DATEI.name} gibt es schon, nichts überschrieben.")
        return
    # Pro Rolle ein Zufallspasswort mit 24 Zeichen (18 Byte Zufall).
    zeilen = ["# SENTINEL Funk: Passwörter der MQTT-Rollen. NIE ins Git, nie weitergeben.",
              "# Neu erzeugen: Datei löschen, dann  bash funk.sh schluessel"]
    for rolle, (zweck, _) in ROLLEN.items():
        zeilen.append(f"MQTT_PASS_{rolle.upper()}={secrets.token_urlsafe(18)}")
    geheim_schreiben(PASSWORT_DATEI, "\n".join(zeilen) + "\n")
    print(f"{PASSWORT_DATEI.name} angelegt: {len(ROLLEN)} Zufallspasswörter, Rechte 600.")


# Text der ACL-Datei für Mosquitto aus der Rollentabelle bauen.
def acl_text():
    teile = ["# SENTINEL Funk: Rechte pro Benutzer. Erzeugt von funk_sicherheit.py, nicht von Hand ändern."]
    for rolle, (zweck, regeln) in ROLLEN.items():
        teile.append(f"\n# {zweck}\nuser {rolle}")
        teile += [f"topic {regel}" for regel in regeln]
    return "\n".join(teile) + "\n"


# Prüft, ob wir root sind. Nur root darf in /etc/mosquitto schreiben.
def root_pruefen():
    if os.geteuid() != 0:
        sys.exit("Bitte mit sudo starten:  sudo python3 funk_sicherheit.py " + sys.argv[1])


# Datei in /etc/mosquitto schreiben: Besitzer root, Gruppe mosquitto, Rechte 640.
# So kann der Broker sie lesen, normale Benutzer aber nicht.
def mosq_datei(pfad, text):
    pfad.write_text(text, encoding="utf-8")
    subprocess.run(["chown", "root:mosquitto", str(pfad)], check=True)
    os.chmod(pfad, 0o640)


# Mosquitto neu starten und prüfen, ob er läuft.
def mosquitto_neu():
    subprocess.run(["systemctl", "restart", "mosquitto"], check=True)
    ok = subprocess.run(["systemctl", "is-active", "--quiet", "mosquitto"]).returncode == 0
    print("Mosquitto läuft." if ok else "Mosquitto startet nicht! Siehe: journalctl -u mosquitto")
    return ok


# Unterbefehl "broker": Login und Rechte einschalten.
def broker():
    root_pruefen()
    # Passwörter lesen und prüfen, ob für jede Rolle eins da ist.
    pw = env_lesen(PASSWORT_DATEI)
    fehlen = [r for r in ROLLEN if not pw.get(f"MQTT_PASS_{r.upper()}")]
    if fehlen:
        sys.exit(f"In {PASSWORT_DATEI.name} fehlen Passwörter für: {', '.join(fehlen)}. Erst: bash funk.sh schluessel")
    # 1. Passwortdatei: erst "benutzer:klartext" schreiben (nur root und mosquitto lesbar) ...
    mosq_datei(MOSQ_PASSWD, "".join(f"{r}:{pw[f'MQTT_PASS_{r.upper()}']}\n" for r in ROLLEN))
    # ... dann wandelt mosquitto_passwd -U jedes Klartext-Passwort in einen Hash um (PBKDF2-SHA512).
    # So steht kein Passwort auf der Kommandozeile, wo es andere in der Prozessliste sehen könnten.
    subprocess.run(["mosquitto_passwd", "-U", str(MOSQ_PASSWD)], check=True)
    # mosquitto_passwd setzt die Rechte zurück, deshalb noch einmal Gruppe und 640.
    subprocess.run(["chown", "root:mosquitto", str(MOSQ_PASSWD)], check=True)
    os.chmod(MOSQ_PASSWD, 0o640)
    # 2. Rechte-Datei (ACL) aus der Rollentabelle.
    mosq_datei(MOSQ_ACL, acl_text())
    # 3. Broker-Einstellung: anonym verboten, Passwort- und Rechte-Datei benutzen.
    MOSQ_CONF.write_text(
        "# LF07 SENTINEL Funk, abgesichert (Tag 8). Erzeugt von funk_sicherheit.py\n"
        "per_listener_settings false\n"
        "allow_anonymous false\n"
        f"password_file {MOSQ_PASSWD}\n"
        f"acl_file {MOSQ_ACL}\n"
        "listener 1883\n"
        "listener 9001\n"
        "protocol websockets\n", encoding="utf-8")
    print(f"Broker abgesichert: {len(ROLLEN)} Benutzer, anonym verboten.")
    return mosquitto_neu()


# Unterbefehl "offen": zurück zum Stand von Tag 5 (ohne Login). Nur für Notfälle in der Vorführung.
def offen():
    root_pruefen()
    MOSQ_CONF.write_text("# LF07 SENTINEL Funk, OFFEN (wie Tag 5): jeder darf alles\n"
                         "listener 1883\nallow_anonymous true\nlistener 9001\nprotocol websockets\n",
                         encoding="utf-8")
    print("ACHTUNG: Broker ist wieder offen, jeder im Netz darf lesen und senden.")
    return mosquitto_neu()


# Unterbefehl "notebook": Zugang fürs Notebook in einen eigenen Ordner schreiben.
# Das Notebook bekommt NUR das Sender-Passwort (so wenig Rechte wie möglich).
def notebook(ordner, host):
    ziel = Path(ordner).expanduser()
    ziel.mkdir(parents=True, exist_ok=True)
    pw = env_lesen(PASSWORT_DATEI).get("MQTT_PASS_SENDER")
    if not pw:
        sys.exit("Kein Sender-Passwort. Erst: bash funk.sh schluessel")
    # .env mit der Adresse des Pi (vom Notebook aus gesehen).
    (ziel / ".env").write_text(ENV_VORLAGE.replace("MQTT_HOST=localhost", f"MQTT_HOST={host}"), encoding="utf-8")
    # .env.password mit genau einer Zeile.
    geheim_schreiben(ziel / ".env.password",
                     "# Nur der Sender-Zugang fürs Notebook. Nie ins Git.\n" f"MQTT_PASS_SENDER={pw}\n")
    print(f"Notebook-Zugang liegt in {ziel}: .env (MQTT_HOST={host}) und .env.password (nur Rolle sender).")
    print("Beide Dateien neben sender.py legen. Übertragen per LocalSend, nicht über GitHub.")


# Unterbefehl "rechte": Tabelle der Rollen anzeigen.
def rechte():
    for rolle, (zweck, regeln) in ROLLEN.items():
        print(f"{rolle:<8} {zweck}")
        for regel in regeln:
            print(f"         {regel}")


# Das Hauptprogramm.
def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    unter = p.add_subparsers(dest="befehl", required=True)
    unter.add_parser("schluessel")
    unter.add_parser("broker")
    unter.add_parser("offen")
    nb = unter.add_parser("notebook")
    nb.add_argument("ordner")
    nb.add_argument("--host", default="raspberrypi.local", help="Adresse des Pi vom Notebook aus")
    unter.add_parser("rechte")
    a = p.parse_args()
    # Den passenden Unterbefehl ausführen.
    if a.befehl == "schluessel":
        schluessel()
    elif a.befehl == "broker":
        sys.exit(0 if broker() else 1)
    elif a.befehl == "offen":
        sys.exit(0 if offen() else 1)
    elif a.befehl == "notebook":
        notebook(a.ordner, a.host)
    else:
        rechte()


# Nur beim direkten Start ausführen.
if __name__ == "__main__":
    main()
