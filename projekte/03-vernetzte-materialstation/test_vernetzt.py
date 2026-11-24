"""Tests für Projekt 03: Vertrag, Leitstelle und ein echter Durchlauf über Mosquitto.

Die Pins sind simuliert, der Broker ist echt (Mosquitto auf dem Pi, localhost:1883).
Läuft kein Broker, wird der Durchlauf-Teil übersprungen und das gemeldet.
Aufruf: python3 test_vernetzt.py
"""
import json                                    # Payloads für Negativtests bauen
import socket                                  # prüfen, ob ein Broker erreichbar ist
import sys                                     # Suchpfad und Exit-Code
import time                                    # Wartezeiten
from pathlib import Path                       # Pfade

HIER = Path(__file__).resolve().parent         # Ordner dieses Tests
sys.path.insert(0, str(HIER))                  # Projektdateien importierbar
sys.path.insert(0, str(HIER.parent / "gemeinsam"))  # gemeinsame Bausteine importierbar

from gpiozero import Device                    # noqa: E402  globale Pin-Fabrik
from gpiozero.pins.mock import MockFactory     # noqa: E402  simulierte Pins

Device.pin_factory = MockFactory()             # keine echte Hardware nötig

import pinplan                                 # noqa: E402  Pinnummern
import vertrag                                 # noqa: E402  Vertrag
from leitstelle import Leitstelle              # noqa: E402  Empfangslogik
from mqtt_verbindung import BROKER, PORT, neuer_client  # noqa: E402  Broker-Daten

fehler = 0                                     # Fehlerzähler


def pruefe(name, ok):                          # Ergebniszeile ausgeben und Fehler zählen
    global fehler                              # globalen Zähler ändern
    print(("OK     " if ok else "FEHLER ") + name)  # Zeile
    fehler += 0 if ok else 1                   # zählen


# ---------- Vertrag ----------
t = vertrag.topic("material", "request")       # Topic für Materialanforderungen
pruefe("Topic laut Katalog", t == "sentinel/lab01/material/station01/request")  # exakter String
d = vertrag.nachricht("material", "material_request", "active", request_count=1)  # gültige Nachricht
pruefe("gültige Nachricht besteht die Prüfung", vertrag.pruefen(t, d) == ("material", "request"))  # keine Ausnahme
for name, kaputt in [                          # Liste von Negativfällen: (Beschreibung, veränderte Daten)
    ("fehlende message_id wird abgewiesen", {k: v for k, v in d.items() if k != "message_id"}),  # Pflichtfeld entfernt
    ("request_count als Text wird abgewiesen", {**d, "request_count": "3"}),  # Zahl als Text
    ("request_count als bool wird abgewiesen", {**d, "request_count": True}),  # True ist in Python auch eine Zahl, darf aber nicht durchgehen
    ("Ortszeit ohne Z wird abgewiesen", {**d, "timestamp": "2026-11-24T10:00:00"}),  # ohne Zeitzone
    ("unbekannter Status wird abgewiesen", {**d, "status": "kaputt"}),  # nicht in der Werteliste
    ("falsche device_id wird abgewiesen", {**d, "device_id": "door01"}),  # Gerät gehört zu einem anderen Modul
    ("PIN im Payload wird abgewiesen", {**d, "pin": "1234"}),  # Geheimnis im Payload
]:  # Ende der Liste, Schleife beginnt
    try:                                       # Prüfung muss scheitern
        vertrag.pruefen(t, kaputt)             # sollte VertragsFehler werfen
        pruefe(name, False)                    # kam keiner: Test fehlgeschlagen
    except ValueError:                         # VertragsFehler oder UUID-Fehler
        pruefe(name, True)                     # wie erwartet abgewiesen
try:                                           # Topic mit Großbuchstaben
    vertrag.pruefen("sentinel/lab01/Material/station01/request", d)  # sollte scheitern
    pruefe("Topic mit Großbuchstaben wird abgewiesen", False)  # kam keine Ausnahme
except ValueError:                             # erwartet
    pruefe("Topic mit Großbuchstaben wird abgewiesen", True)  # bestanden

# ---------- Leitstelle ----------
l = Leitstelle()                               # Empfangslogik ohne Netzwerk
roh = json.dumps(d).encode()                   # gültige Nachricht als Bytes
pruefe("Leitstelle nimmt gültige Nachricht an", l.verarbeiten(t, roh) == "ok")  # erste Lieferung
pruefe("Leitstelle erkennt Duplikat", l.verarbeiten(t, roh) == "duplikat")  # gleiche message_id noch einmal
pruefe("Leitstelle weist kaputtes JSON ab", l.verarbeiten(t, b"{kein json") == "abgewiesen")  # Parserfehler
pruefe("Leitstelle zählt richtig", (l.gueltig, l.duplikate, l.abgewiesen) == (1, 1, 1))  # Bilanz

# ---------- Durchlauf über den echten Broker ----------
try:                                           # ist ein Broker erreichbar?
    socket.create_connection((BROKER, PORT), timeout=1).close()  # nur kurz anklopfen
    broker_da = True                           # ja
except OSError:                                # nein
    broker_da = False                          # dann überspringen
if not broker_da:                              # kein Broker
    print(f"HINWEIS Durchlauf übersprungen, kein Broker auf {BROKER}:{PORT}")  # ehrlich melden
else:                                          # Broker vorhanden
    from materialstation_mqtt import Materialstation  # erst hier importieren, braucht paho
    empfang = Leitstelle()                     # eigene Leitstelle für den Test
    sub = neuer_client("test-leitstelle")      # Test-Subscriber
    sub.on_message = lambda c, u, m: empfang.verarbeiten(m.topic, m.payload, m.retain)  # Nachrichten an die Logik
    sub.connect(BROKER, PORT)                  # verbinden
    sub.subscribe("sentinel/lab01/material/#", qos=1)  # nur Material-Topics
    sub.loop_start()                           # Netzwerk-Thread
    time.sleep(0.5)                            # Abo wirksam werden lassen
    station = Materialstation()                # Station mit simulierten Pins
    station.starten()                          # verbinden
    pin = Device.pin_factory.pin(pinplan.TASTER)  # simulierter Taster
    for _ in range(3):                         # drei Drücke
        pin.drive_low()                        # drücken
        time.sleep(0.1)                        # halten
        pin.drive_high()                       # loslassen
        time.sleep(0.4)                        # Zeit für Senden und Quittung
    time.sleep(1.0)                            # letzte Nachrichten ankommen lassen
    pruefe("drei Anforderungen vom Broker quittiert", station.gesendet == 3)  # PUBACK für alle drei
    station.beenden()                          # geordnet beenden: offline retained
    time.sleep(0.5)                            # Status ankommen lassen
    sub.loop_stop()                            # Subscriber stoppen
    sub.disconnect()                           # trennen
    pruefe("Leitstelle hat drei Anforderungen und Status-Meldungen gültig erhalten", empfang.gueltig >= 5 and empfang.abgewiesen == 0)  # 3 request + online + offline

print()                                        # Leerzeile
print("Alle Tests bestanden." if fehler == 0 else f"{fehler} Test(s) fehlgeschlagen.")  # Fazit
sys.exit(1 if fehler else 0)                   # Exit-Code
