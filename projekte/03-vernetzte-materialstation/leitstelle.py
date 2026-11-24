"""SENTINEL Leitstelle: externer Subscriber, der jede Nachricht gegen den Vertrag prüft.

Abonniert sentinel/lab01/# und zeigt jede gültige Nachricht an. Ungültige Nachrichten
werden mit Grund abgewiesen und nie fachlich verarbeitet. Eine bereits bekannte
message_id wird als Duplikat erkannt und nicht doppelt gezählt (Vertrag 3.8).

Aufruf:  python3 leitstelle.py              (auf dem Pi oder einem zweiten Rechner)
         SENTINEL_BROKER=<IP-des-Pi> python3 leitstelle.py
"""
import sys                                     # Suchpfad
from collections import OrderedDict            # Gedächtnis für message_ids mit fester Größe
from pathlib import Path                       # Pfade

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gemeinsam"))  # projekte/gemeinsam importierbar machen

import vertrag                                 # noqa: E402  Prüfregeln
from mqtt_verbindung import BROKER, PORT, neuer_client  # noqa: E402  gleiche Broker-Einstellung wie die Module

GEDAECHTNIS = 1000                             # so viele message_ids werden gemerkt


class Leitstelle:                              # Empfangslogik getrennt vom Netzwerk, damit man sie testen kann
    def __init__(self):                        # Startzustand
        self.bekannt = OrderedDict()           # message_id -> True, älteste zuerst
        self.gueltig = 0                       # Anzahl gültiger, neuer Nachrichten
        self.abgewiesen = 0                    # Anzahl ungültiger Nachrichten
        self.duplikate = 0                     # Anzahl doppelter Nachrichten

    def verarbeiten(self, topic, roh, retained=False):  # eine Nachricht prüfen und einordnen
        if not roh:                            # leere Payload = gelöschter Retain-Wert
            return "geloescht"                 # nichts zu prüfen
        try:                                   # Vertragsprüfung kann fehlschlagen
            daten = vertrag.aus_json(topic, roh)  # JSON parsen und gegen den Vertrag prüfen
        except (ValueError, UnicodeDecodeError) as fehler:  # VertragsFehler ist auch ein ValueError
            self.abgewiesen += 1               # zählen
            print(f"ABGEWIESEN {topic}: {fehler}")  # Grund zeigen, Payload nicht verarbeiten
            return "abgewiesen"                # Ergebnis für den Test
        mid = daten["message_id"]              # eindeutige ID der Nachricht
        if mid in self.bekannt:                # schon einmal gesehen (QoS 1 kann doppelt liefern)
            self.duplikate += 1                # zählen
            print(f"DUPLIKAT  {topic}: {mid}") # protokollieren, aber nicht erneut ausführen
            return "duplikat"                  # Ergebnis für den Test
        self.bekannt[mid] = True               # ID merken
        if len(self.bekannt) > GEDAECHTNIS:    # Gedächtnis voll?
            self.bekannt.popitem(last=False)   # älteste ID vergessen
        self.gueltig += 1                      # zählen
        merkmal = " (retained)" if retained else ""  # retained Werte kennzeichnen (Retain-Test)
        extra = {k: v for k, v in daten.items() if k not in vertrag.PFLICHTFELDER}  # nur modulspezifische Felder zeigen
        print(f"OK {self.gueltig:3d}  {daten['timestamp']}  {topic}  {daten['event_type']}/{daten['status']}{merkmal}  {extra}")  # Anzeige
        return "ok"                            # Ergebnis für den Test


def main():                                    # Netzwerkteil
    leitstelle = Leitstelle()                  # Empfangslogik
    client = neuer_client("sentinel-leitstelle")  # eigener Client-Name
    client.on_connect = lambda c, u, f, rc: c.subscribe("sentinel/lab01/#", qos=1)  # nach dem Verbinden alles unter lab01 abonnieren
    client.on_message = lambda c, u, m: leitstelle.verarbeiten(m.topic, m.payload, m.retain)  # jede Nachricht an die Logik geben
    client.connect(BROKER, PORT, keepalive=30) # verbinden (wirft, wenn der Broker fehlt)
    print(f"Leitstelle hört auf sentinel/lab01/# bei {BROKER}:{PORT}. Strg+C beendet.")  # Startmeldung
    try:                                       # geschützter Block
        client.loop_forever()                  # Netzwerkschleife im Hauptthread
    except KeyboardInterrupt:                  # Strg+C
        print(f"\nGültig: {leitstelle.gueltig}, abgewiesen: {leitstelle.abgewiesen}, Duplikate: {leitstelle.duplikate}")  # Bilanz
    finally:                                   # Aufräumen
        client.disconnect()                    # sauber trennen


if __name__ == "__main__":                     # nur beim direkten Start
    main()                                     # los geht's
