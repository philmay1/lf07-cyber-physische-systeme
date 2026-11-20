#!/usr/bin/env python3
"""Test für SENTINEL Funk, ohne Broker und ohne echte Datenbanken.

Start:  python3 test_funk.py
Prüft Payload-Lesen, PIN-Schutz, Speichern, die Subscriber-Funktion, die Brücke
mit Sperre nach 3 Fehlversuchen und die Web-Adressen.
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er erklärt, was getestet wird.

# os setzt Umgebungsvariablen, bevor unsere Module geladen werden.
import os

# tempfile legt einen Wegwerf-Ordner für die Test-Datenbanken an.
import tempfile

# Path baut die Pfade.
from pathlib import Path

# Wegwerf-Ordner anlegen.
TMP = Path(tempfile.mkdtemp())
# Beide Datenbanken in den Wegwerf-Ordner umlenken. Die echten bleiben unberührt.
os.environ["FUNK_DB"] = str(TMP / "mqtt_test.db")
os.environ["ZUTRITT_DB"] = str(TMP / "zutritt_test.db")

# Erst jetzt unsere Module laden, damit sie die Test-Pfade übernehmen.
import funk_db as fdb                 # noqa: E402
import mqtt_logger                    # noqa: E402
import zutritt_bruecke as br          # noqa: E402
import zutritt_db as zdb              # noqa: E402
import funk_web                       # noqa: E402

# Zähler für bestandene Prüfungen.
ok = 0


# Kleine Prüf-Funktion: Bedingung muss stimmen, sonst bricht der Test mit Meldung ab.
def pruefe(bedingung, text):
    global ok
    assert bedingung, "FEHLER: " + text
    ok += 1
    print("ok  ", text)


# Ersatz für eine echte MQTT-Nachricht: hat nur topic und payload.
class Nachricht:
    def __init__(self, topic, payload):
        self.topic, self.payload = topic, payload


# 1. Payload lesen: JSON, reiner Text, PIN-Schutz.
pruefe(fdb.payload_lesen("lf07/handy/lisa/knopf", b'{"wert": "Hallo", "sender": "Lisa"}') == ("Hallo", "Lisa"),
       "JSON mit wert und sender wird gelesen")
pruefe(fdb.payload_lesen("lf07/nb1/text", b"23.5") == ("23.5", "nb1"),
       "reiner Text: Sender kommt aus dem Topic")
pruefe(fdb.payload_lesen("lf07/zutritt/pin", b'{"wert": "4711", "sender": "Tom"}')[0] == "PIN ****",
       "PIN wird nur als **** gespeichert")

# 2. Die Subscriber-Funktion schreibt 20 Events in die Datenbank.
con = fdb.verbinden()
for i in range(20):
    mqtt_logger.beim_empfang(None, con, Nachricht(f"lf07/test/wert", f'{{"wert": {i}, "sender": "Test"}}'.encode()))
pruefe(fdb.anzahl(con) == 20, "beim_empfang() hat 20 Events gespeichert")
letzte = fdb.letzte_events(con, 1)[0]
pruefe(letzte["wert"] == "19" and letzte["topic"] == "lf07/test/wert" and letzte["zeit"] > 0,
       "neuestes Event hat Wert, Topic und Zeit")
pruefe(len(letzte["uhrzeit"]) == 8, "Uhrzeit wird als HH:MM:SS geliefert")

# 3. Brücke: richtige PIN, dann 3 falsche -> Sperre.
zcon = zdb.verbinden()
zdb.benutzer_anlegen(zcon, "Testadmin", "2468", "admin")
a = br.pin_verarbeiten(zcon, {"wert": "2468", "sender": "Lisa"})
pruefe(a["ergebnis"] == "ok" and a["name"] == "Testadmin", "richtige PIN per MQTT: Zutritt")
a = br.pin_verarbeiten(zcon, {"wert": "4711", "sender": "Tom"})
pruefe(a["ergebnis"] == "falsch" and a["fehlversuche"] == 1, "1. falsche PIN wird gezählt")
br.pin_verarbeiten(zcon, {"wert": "1234", "sender": "Tom"})
a = br.pin_verarbeiten(zcon, {"wert": "0007", "sender": "Tom"})
pruefe(a["ergebnis"] == "gesperrt" and a["neu"] and a["rest"] > 0, "3. falsche PIN sperrt (neu=True)")
a = br.pin_verarbeiten(zcon, {"wert": "2468", "sender": "Lisa"})
pruefe(a["ergebnis"] == "gesperrt" and not a["neu"], "während der Sperre hilft auch die richtige PIN nicht")
a = br.pin_verarbeiten(zdb.verbinden(), {"wert": "abc"})
pruefe(a["ergebnis"] == "gesperrt", "auch Unsinn ändert nichts an der Sperre")
hinweis = zcon.execute("SELECT hinweis FROM versuche WHERE erfolg = 0 ORDER BY id LIMIT 1").fetchone()[0]
pruefe("per MQTT von Tom" in hinweis, "SENTINEL-Protokoll zeigt, von welchem Handy der Versuch kam")

# 4. Web: Seiten und Daten.
web = funk_web.app.test_client()
d = web.get("/api/events").get_json()
pruefe(d["anzahl"] == 20 and len(d["events"]) == 10, "/api/events liefert Anzahl und die letzten 10")
pruefe(b"SENTINEL FUNK" in web.get("/").data, "Board-Seite wird ausgeliefert")
pruefe(b"Knack den Tresor" in web.get("/handy").data, "Handy-Seite wird ausgeliefert")
pruefe(web.get("/static/mqtt.min.js").status_code == 200, "mqtt.min.js liegt lokal (kein Internet nötig)")
pruefe(web.get("/api/info").get_json()["handy_url"].endswith(":5050/handy"), "Handy-Adresse für den QR-Code")
pruefe(web.get("/qr.svg").status_code in (200, 404), "QR-Code-Adresse antwortet")

# 5. Leeren für eine frische Vorführung.
fdb.leeren(con)
pruefe(fdb.anzahl(con) == 0, "leeren() löscht alle Events")

print(f"\nAlle {ok} Prüfungen bestanden.")
