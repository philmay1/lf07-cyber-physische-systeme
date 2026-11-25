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
# Test-Passwörter für alle Rollen. Gesetzte Variablen gewinnen gegen eine echte .env.password.
for _r in ("logger", "board", "bruecke", "keypad", "sender", "handy"):
    os.environ[f"MQTT_PASS_{_r.upper()}"] = f"testpasswort-{_r}-123"

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

# 5. Absicherung (Tag 8): Rollen, Rechte, Zugang im Browser, Commit-Wächter.
import funk_sicherheit as fs          # noqa: E402
import importlib.util                 # noqa: E402
pruefe(fdb.zugang("logger") == ("logger", "testpasswort-logger-123"), "zugang() liest das Passwort der Rolle aus der Umgebung")
pruefe(fdb.zugang("gibtsnicht") is None, "Rolle ohne Passwort: kein Login (Betrieb wie Tag 5)")
acl = fs.acl_text()
pruefe("user board" in acl and "topic read lf07/zutritt/pin" not in acl.split("user board")[1].split("user ")[0],
       "ACL: Board darf PINs nicht lesen")
pruefe("topic write lf07/keypad/versuch" in acl.split("user keypad")[1].split("user ")[0] and acl.count("write lf07/keypad") == 1,
       "ACL: nur die Rolle keypad darf Keypad-Meldungen senden")
seite = web.get("/").data.decode("utf-8")
pruefe("testpasswort-board-123" in seite and "__ZUGANG__" not in seite, "Board-Seite bekommt den Board-Zugang eingesetzt")
fremde = [r for r in ("logger", "bruecke", "keypad", "sender", "handy") if f"testpasswort-{r}-123" in seite]
pruefe(not fremde, "Board-Seite enthält keine anderen Passwörter")
handy_seite = web.get("/handy").data.decode("utf-8")
pruefe("testpasswort-handy-123" in handy_seite and "testpasswort-logger-123" not in handy_seite, "Handy-Seite: nur Handy-Zugang")
spec = importlib.util.spec_from_file_location("waechter", Path(__file__).resolve().parents[2] / ".githooks" / "geheimnis_waechter.py")
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
pruefe(all(w.geheimer_name(n) for n in (".env", ".env.password", "uebungen/x/.env.local", "access.env")),
       "Wächter erkennt .env, .env.password, .env.local, access.env")
pruefe(not w.geheimer_name(".env.example") and not w.geheimer_name("funk_db.py"), "Wächter lässt .env.example und Code durch")
probe = TMP / ".env.password"
probe.write_text("MQTT_PASS_X=abcdefgh123\nKURZ=abc\n", encoding="utf-8")
pruefe(w.geheimnisse_aus(probe, alle_werte=True) == {"abcdefgh123": (probe, "MQTT_PASS_X")}, "Wächter sammelt Passwörter, ignoriert zu kurze Werte")
probe2 = TMP / "einstellungen.env"
probe2.write_text("MQTT_HOST=raspberrypi.local\nDB_PASSWORT=sehr-geheim-99\n", encoding="utf-8")
pruefe(list(w.geheimnisse_aus(probe2, alle_werte=False)) == ["sehr-geheim-99"], "in normaler .env nur Variablen mit PASS/TOKEN/KEY")

# 6. Leeren für eine frische Vorführung.
fdb.leeren(con)
pruefe(fdb.anzahl(con) == 0, "leeren() löscht alle Events")

print(f"\nAlle {ok} Prüfungen bestanden.")
