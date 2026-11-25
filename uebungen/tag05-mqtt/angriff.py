#!/usr/bin/env python3
"""Angriffstest für SENTINEL Funk: Hält die Absicherung, was sie verspricht? (Tag 8)

Start auf dem Pi:  bash funk.sh angriff   (oder python3 angriff.py)

Probiert typische Angriffe gegen den echten Broker und das Git-Repo aus und zeigt
für jeden Versuch grün (abgewehrt) oder rot (Lücke). Es werden keine PINs geprüft
und nichts an der Zutrittskontrolle verändert.
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er erklärt, was der Test macht.

# os liest Umgebungsvariablen und Dateirechte.
import os

# stat wertet Dateirechte aus (z. B. 600).
import stat

# subprocess ruft git auf.
import subprocess

# threading.Event wartet auf Antworten des Brokers.
import threading

# time wartet kurz, bis Nachrichten angekommen sind.
import time

# Path baut Pfade.
from pathlib import Path

# Unsere gemeinsame Datei: lädt .env und .env.password und baut MQTT-Clients.
import funk_db as fdb

# Farben fürs Terminal: grün, rot, gelb, zurücksetzen.
GRUEN, ROT, GELB, AUS = "\033[92m", "\033[91m", "\033[93m", "\033[0m"
# Ordner dieses Skripts.
HIER = Path(__file__).resolve().parent
# Ergebnisliste: (bestanden ja/nein/None, Text).
ergebnisse = []


# Ein Ergebnis festhalten und sofort anzeigen. ok=None heißt: übersprungen.
def melden(ok, text):
    ergebnisse.append(ok)
    zeichen = f"{GRUEN}✔ abgewehrt{AUS}" if ok else (f"{GELB}– übersprungen{AUS}" if ok is None else f"{ROT}✘ LÜCKE{AUS}    ")
    print(f"  {zeichen}  {text}")


# Versucht eine Verbindung und gibt den Antwortcode des Brokers zurück (0 = angenommen).
def verbinden(benutzer=None, passwort=None):
    c = fdb.client_bauen("angriff", rolle="niemand")   # Rolle ohne Passwort: wir setzen den Login selbst
    if benutzer:
        c.username_pw_set(benutzer, passwort)
    antwort, fertig = {}, threading.Event()
    # Rückruf: Antwortcode merken. properties=None für paho 2.x.
    def auf_connect(client, userdata, flags, rc, properties=None):
        antwort["rc"] = int(getattr(rc, "value", rc))
        fertig.set()
    c.on_connect = auf_connect
    c.connect(fdb.MQTT_HOST, fdb.MQTT_PORT, keepalive=10)
    c.loop_start()
    fertig.wait(5)
    return c, antwort.get("rc", -1)


# Client einer echten Rolle mit ihrem Passwort aus .env.password.
def rolle(name):
    login = fdb.zugang(name)
    c, rc = verbinden(*login) if login else (None, -1)
    return c, rc


# Abonniert ein Topic und gibt zurück, was der Broker bewilligt hat (128 = verweigert),
# plus eine Liste, in der alle empfangenen Nachrichten landen.
def abonnieren(c, topic):
    empfangen, bewilligt, fertig = [], {}, threading.Event()
    c.on_message = lambda client, u, msg: empfangen.append(msg.payload.decode("utf-8", "replace"))
    # paho 1.x schickt eine Liste von Zahlen, paho 2.x eine Liste von Objekten.
    def auf_sub(client, u, mid, erteilt, properties=None):
        bewilligt["qos"] = int(getattr(erteilt[0], "value", erteilt[0]))
        fertig.set()
    c.on_subscribe = auf_sub
    c.subscribe(topic, qos=1)
    fertig.wait(5)
    return bewilligt.get("qos", -1), empfangen


# Sendet als Rolle und prüft, ob der Lauscher (Rolle logger, liest alles) die Nachricht bekommt.
def kommt_an(sender_client, lauscher_liste, topic, marke):
    sender_client.publish(topic, f'{{"wert": "{marke}", "sender": "Angriffstest"}}', qos=1)
    time.sleep(1.0)
    return any(marke in n for n in lauscher_liste)


# Führt einen git-Befehl im Repo aus und gibt (Rückgabecode, Ausgabe) zurück.
def git(*argumente):
    r = subprocess.run(["git", *argumente], cwd=HIER, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    print(f"\nAngriffstest gegen {fdb.MQTT_HOST}:{fdb.MQTT_PORT} und das Git-Repo\n")
    if not fdb.zugang("logger"):
        print(f"{ROT}Keine .env.password gefunden. Erst: bash funk.sh schluessel{AUS}")
        return 1

    # --- 1. Wer darf überhaupt rein? ---
    print("Wer darf rein?")
    c, rc = verbinden()
    melden(rc != 0, f"anonym verbinden (ohne Login)            Broker-Code {rc}")
    c.loop_stop()
    c, rc = verbinden("sender", "falsches-passwort-123")
    melden(rc != 0, f"Benutzer sender mit falschem Passwort    Broker-Code {rc}")
    c.loop_stop()
    c, rc = verbinden("admin", "admin")
    melden(rc != 0, f"Standard-Login admin/admin               Broker-Code {rc}")
    c.loop_stop()

    # --- 2. Darf jede Rolle nur, was sie soll? ---
    print("\nDarf jede Rolle nur, was sie soll? (Lauscher: Rolle logger)")
    lauscher, rc = rolle("logger")
    _, gehoert = abonnieren(lauscher, "lf07/#")
    handy, _ = rolle("handy")
    board, _ = rolle("board")
    sender, _ = rolle("sender")
    marke = f"test{int(time.time())}"
    # Gegenprobe: erlaubtes Senden muss ankommen, sonst wäre der Test wertlos.
    erlaubt = kommt_an(handy, gehoert, "lf07/handy/Angriffstest/knopf", marke + "a")
    print(f"  {'✔' if erlaubt else '✘'} Gegenprobe: Handy sendet einen Knopf, der kommt an: {'ja' if erlaubt else 'NEIN'}")
    melden(not kommt_an(handy, gehoert, "lf07/keypad/versuch", marke + "b"),
           "Handy fälscht eine Keypad-Meldung (lf07/keypad/versuch)")
    melden(not kommt_an(board, gehoert, "lf07/handy/Gast/knopf", marke + "c"),
           "Board (nur lesen) versucht zu senden")
    melden(not kommt_an(sender, gehoert, "lf07/zutritt/antwort/x", marke + "d"),
           "Sender gibt sich als SENTINEL aus (falsche Antwort ans Handy)")
    # Darf das Board PINs mitlesen? Der Broker muss das Abo verweigern (128) oder nichts liefern.
    qos, board_hoert = abonnieren(board, "lf07/zutritt/pin")
    handy.publish("lf07/zutritt/pin", "angriffstest-keine-pin", qos=1)   # kein JSON: die Brücke ignoriert das
    time.sleep(1.0)
    melden(qos == 128 or not board_hoert, f"Board will PINs mitlesen (lf07/zutritt/pin)  Abo-Code {qos}")
    for c in (lauscher, handy, board, sender):
        c.loop_stop()
        c.disconnect()

    # --- 3. Bleiben die Geheimnisse aus Git heraus? ---
    print("\nBleiben die Geheimnisse aus Git heraus?")
    for name in (".env", ".env.password"):
        rc, _ = git("check-ignore", "-q", name)
        melden(rc == 0, f"{name} wird von .gitignore gesperrt")
    _, liste = git("ls-files")
    verfolgt = [z for z in liste.splitlines() if Path(z).name.startswith(".env") and Path(z).name != ".env.example"]
    melden(not verfolgt, "keine echte .env-Datei im Repo" + (f": {verfolgt}" if verfolgt else ""))
    rechte = stat.S_IMODE(os.stat(HIER / ".env.password").st_mode)
    melden(rechte == 0o600, f".env.password nur für den Besitzer lesbar (Rechte {rechte:o})")

    # --- 4. Commit-Wächter: Passwort im Code darf nicht committet werden ---
    _, hooks = git("config", "core.hooksPath")
    if hooks != ".githooks":
        melden(None, "Commit-Wächter ist aus. Einschalten: bash funk.sh waechter")
    else:
        leck = HIER / "leck_test.py"
        leck.write_text(f'PASSWORT = "{os.environ["MQTT_PASS_SENDER"]}"   # Absicht: so NIE!\n', encoding="utf-8")
        try:
            git("add", "-f", str(leck))
            rc, ausgabe = git("-c", "user.name=Angriffstest", "-c", "user.email=test@localhost",
                              "commit", "-q", "-m", "Angriffstest: Passwort im Code")
            if rc == 0:
                git("reset", "-q", "--soft", "HEAD~1")   # versehentlichen Commit sofort zurücknehmen
            melden(rc != 0 and "GESTOPPT" in ausgabe, "Commit mit Passwort im Code (leck_test.py)")
        finally:
            git("reset", "-q", "--", str(leck))
            leck.unlink(missing_ok=True)

    # --- Zusammenfassung ---
    gezaehlt = [e for e in ergebnisse if e is not None]
    gut = sum(gezaehlt)
    farbe = GRUEN if gut == len(gezaehlt) and erlaubt else ROT
    print(f"\n{farbe}{gut} von {len(gezaehlt)} Angriffen abgewehrt.{AUS}\n")
    return 0 if gut == len(gezaehlt) else 1


# Nur beim direkten Start ausführen.
if __name__ == "__main__":
    raise SystemExit(main())
