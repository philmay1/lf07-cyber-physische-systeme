#!/usr/bin/env python3
"""Brücke Handy -> SENTINEL: PINs, die per MQTT kommen, prüft die echte Zutrittskontrolle.

Ein Handy schickt auf lf07/zutritt/pin z. B. {"wert": "4711", "sender": "Lisa", "antwort": "abc"}.
Die Brücke prüft die PIN gegen zutritt.db aus Tag 5 (dieselbe Sperre nach 3 Fehlversuchen)
und antwortet auf lf07/zutritt/antwort/abc. Das SENTINEL-Dashboard zeigt den Alarm,
die rote LED am Pi geht an, wenn zutritt.py läuft.

Start auf dem Pi:  python3 zutritt_bruecke.py
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er erklärt Zweck und Start.

# json liest die Handy-Nachricht und baut die Antwort.
import json

# sys brauchen wir, um den Ordner von Tag 5 in den Suchpfad für Module zu legen.
import sys

# Path baut den Pfad zum Nachbarordner tag05-zutrittskontrolle.
from pathlib import Path

# Unsere gemeinsame Datei mit dem MQTT-Client.
import funk_db as fdb

# Ordner der Zutrittskontrolle (liegt neben diesem Ordner) bekannt machen ...
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tag05-zutrittskontrolle"))
# ... und daraus die Datenbank-Logik mit Sperre laden.
import zutritt_db as zdb  # noqa: E402

# Auf diesem Topic kommen PINs an.
PIN_THEMA = "lf07/zutritt/pin"


# Prüft eine PIN-Nachricht und gibt die Antwort als Wörterbuch zurück.
# Eigene Funktion ohne MQTT, damit der Test sie direkt aufrufen kann.
def pin_verarbeiten(con, daten):
    # PIN und Absender aus der Nachricht holen. Fehlt etwas, wird es ein leerer Text.
    pin = str(daten.get("wert", ""))
    wer = str(daten.get("sender", "Handy"))[:20]
    # Erst nachsehen, ob gerade gesperrt ist. Dann wird gar nicht erst geprüft.
    st = zdb.status(con)
    if st["gesperrt"]:
        # neu=False: Die Sperre bestand schon vorher.
        return {"ergebnis": "gesperrt", "neu": False, "rest": round(st["rest"]),
                "fehlversuche": st["fehlversuche"], "max": zdb.MAX_FEHLVERSUCHE, "name": ""}
    # Nur 1 bis 8 Ziffern sind eine gültige PIN.
    gueltig = pin.isdigit() and 1 <= len(pin) <= 8
    # PIN gegen die Benutzer-Tabelle prüfen. Passt sie, steht der Benutzer in b.
    b = zdb.pin_pruefen(con, pin) if gueltig else None
    # Versuch eintragen. Der Hinweis zeigt im SENTINEL-Protokoll, von welchem Handy es kam.
    ergebnis = zdb.versuch_eintragen(con, b is not None, b, hinweis=f"per MQTT von {wer}")
    # Neuen Stand holen (Fehlversuche, Restzeit).
    st = zdb.status(con)
    # Antwort zusammenbauen. Den Namen gibt es nur bei richtiger PIN.
    # neu=True bei "gesperrt": Genau dieser Versuch hat die Sperre ausgelöst.
    return {"ergebnis": ergebnis, "neu": ergebnis == "gesperrt", "rest": round(st["rest"]), "fehlversuche": st["fehlversuche"],
            "max": zdb.MAX_FEHLVERSUCHE, "name": b["name"] if b else ""}


# Wird nach dem Verbinden aufgerufen: Abo auf das PIN-Topic anlegen.
def verbunden(client, userdata, flags, rc, properties=None):
    # Nur bei erfolgreicher Verbindung (rc 0) abonnieren.
    if rc == 0:
        client.subscribe(PIN_THEMA, qos=1)
        print("Brücke bereit, warte auf PINs auf", PIN_THEMA)
    # Sonst den Grund nennen (z. B. Login falsch).
    else:
        print(fdb.grund(rc))


# Wird für jede PIN-Nachricht aufgerufen.
def beim_empfang(client, userdata, msg):
    # Nachricht als JSON lesen. Kaputte Nachrichten ignorieren.
    try:
        daten = json.loads(msg.payload.decode("utf-8"))
    except ValueError:
        return
    # Nur Objekte wie {"wert": ...} sind gültig.
    if not isinstance(daten, dict):
        return
    # Prüfen lassen. userdata ist die Verbindung zu zutritt.db.
    antwort = pin_verarbeiten(userdata, daten)
    # Ausgabe im Terminal, ohne die PIN zu zeigen.
    print(f"{daten.get('sender', '?'):<14} -> {antwort['ergebnis']}")
    # Hat das Handy eine Antwort-Adresse mitgeschickt? Dann dorthin antworten.
    ziel = str(daten.get("antwort", ""))
    # Nur einfache Namen erlauben, damit niemand in fremde Topics schreibt.
    if ziel.isalnum():
        # von: wer die PIN geschickt hat. Das Board darf PINs selbst nicht lesen, sieht so aber den Namen.
        # wert und sender ergänzen, damit der Logger "gesperrt" von "SENTINEL" speichert.
        antwort.update(wert=antwort["ergebnis"], sender="SENTINEL", von=str(daten.get("sender", ""))[:20])
        client.publish(f"lf07/zutritt/antwort/{ziel}", json.dumps(antwort), qos=1)


# Das Hauptprogramm.
def main():
    # Verbindung zur Datenbank der Zutrittskontrolle.
    con = zdb.verbinden()
    # MQTT-Client anlegen, Datenbank als userdata mitgeben.
    client = fdb.client_bauen("bruecke")
    client.user_data_set(con)
    # Rückrufe eintragen.
    client.on_connect = verbunden
    client.on_message = beim_empfang
    # Verbinden und endlos warten.
    client.connect(fdb.MQTT_HOST, fdb.MQTT_PORT, keepalive=30)
    try:
        client.loop_forever()
    # Strg+C: sauber beenden.
    except KeyboardInterrupt:
        client.disconnect()


# Nur beim direkten Start ausführen, nicht beim Import im Test.
if __name__ == "__main__":
    main()
