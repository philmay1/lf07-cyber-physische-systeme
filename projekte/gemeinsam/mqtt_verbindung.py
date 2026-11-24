"""MQTT-Verbindung für SENTINEL-Module mit Last Will und Status-Topic.

Regeln aus dem Katalog (3.7): online retained nach dem Verbinden, offline retained als
Last Will. Der Broker sendet den Last Will, wenn das Modul ohne Abmeldung verschwindet.
"""
import json                                   # Last-Will-Payload als JSON-Text
import os                                     # Broker-Adresse aus Umgebungsvariablen lesen
import threading                              # Event, das meldet: Verbindung steht
import time                                   # Timeout beim Warten auf die Broker-Bestätigung

import paho.mqtt.client as mqtt               # MQTT-Client-Bibliothek (paho)

import vertrag                                # Topic- und Payload-Regeln aus dem Katalog

BROKER = os.environ.get("SENTINEL_BROKER", "localhost")   # Mosquitto läuft auf dem Pi selbst
PORT = int(os.environ.get("SENTINEL_PORT", "1883"))       # Standardport für MQTT ohne TLS


def neuer_client(name):                       # erzeugt einen Client, der mit paho 1.x und 2.x läuft
    try:                                      # paho 2.x verlangt die Angabe der Callback-Version
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=name)  # gleiche Callback-Form wie 1.x
    except AttributeError:                    # paho 1.x kennt CallbackAPIVersion noch nicht
        return mqtt.Client(client_id=name)    # also ohne diese Angabe


class Modul:                                  # bündelt Verbindung, Status und Senden für ein SENTINEL-Modul
    def __init__(self, modul, name):          # modul z. B. "material", name = eindeutiger Client-Name
        self.modul = modul                    # merken, für welches Modul gesendet wird
        self.status_topic = vertrag.topic(modul, "status")  # z. B. sentinel/lab01/material/station01/status
        self.verbunden = threading.Event()    # wird gesetzt, sobald der Broker die Verbindung bestätigt
        self.client = neuer_client(name)      # paho-Client anlegen
        offline = vertrag.nachricht(modul, "connection_status", "offline")  # Last-Will-Nachricht vorbereiten
        self.client.will_set(self.status_topic, vertrag.als_json(self.status_topic, offline), qos=1, retain=True)  # Broker hebt sie auf
        self.client.on_connect = self._bei_verbindung        # wird nach dem Verbinden aufgerufen
        self.client.on_disconnect = self._bei_trennung       # wird bei jeder Trennung aufgerufen

    def _bei_verbindung(self, client, userdata, flags, rc):  # rc = Reason Code, 0 heißt Erfolg
        if rc == 0:                            # nur bei Erfolg als verbunden markieren
            self.verbunden.set()               # wartende Programmteile freigeben
            self.status("online")              # online retained, wie im Vertrag verlangt
        else:                                  # Broker hat abgelehnt (z. B. falsche Zugangsdaten)
            print(f"MQTT: Verbindung abgelehnt, Code {rc}")  # Code anzeigen, damit man den Grund sieht

    def _bei_trennung(self, client, userdata, rc):  # rc 0 = geordnet getrennt, sonst unerwartet
        self.verbunden.clear()                 # ab jetzt gilt: nicht verbunden
        if rc != 0:                            # nur unerwartete Trennungen melden
            print(f"MQTT: Verbindung verloren (Code {rc}), paho versucht es erneut")  # loop_start verbindet neu

    def starten(self, warten=5.0):             # verbindet und startet den Netzwerk-Thread
        self.client.connect_async(BROKER, PORT, keepalive=30)  # asynchron: blockiert nicht, wenn der Broker fehlt
        self.client.loop_start()               # eigener Thread für Senden, Empfangen und Wiederverbinden
        return self.verbunden.wait(warten)     # True, wenn die Verbindung innerhalb der Wartezeit steht

    def status(self, wert, event_type="connection_status"):  # retained Status-Nachricht senden
        return self.senden("status", vertrag.nachricht(self.modul, event_type, wert))  # über die gemeinsame Sendefunktion

    def senden(self, typ, daten):              # prüft und sendet eine Nachricht nach Vertrag
        thema = vertrag.topic(self.modul, typ)  # Topic aus Modul und Typ bauen
        qos, retain = vertrag.UEBERTRAGUNG[typ]  # QoS und Retain laut Katalog 3.7
        text = vertrag.als_json(thema, daten)  # prüfen und in JSON umwandeln, wirft bei Vertragsfehler
        if not self.verbunden.is_set():        # ohne Verbindung keine Erfolgsmeldung vortäuschen
            print(f"MQTT: nicht verbunden, {typ} nicht gesendet")  # ehrlich melden (Vertrag: keine späte Zustellung behaupten)
            return None                        # Aufrufer weiß: nicht gesendet
        info = self.client.publish(thema, text, qos=qos, retain=retain)  # an den Broker übergeben
        return info if info.rc == mqtt.MQTT_ERR_SUCCESS else None  # Quittungs-Objekt zurück, damit der Aufrufer auf PUBACK warten kann

    def quittiert(self, info, warten=3.0):     # wartet auf die Bestätigung des Brokers (PUBACK bei QoS 1)
        if info is None:                       # gar nicht erst gesendet
            return False                       # also auch nicht quittiert
        ende = time.monotonic() + warten       # spätester Zeitpunkt; paho 1.5 (Pi OS Bullseye) kennt keinen eigenen Timeout
        while not info.is_published() and time.monotonic() < ende:  # warten, bis der Broker bestätigt oder die Zeit um ist
            time.sleep(0.02)                   # kurz schlafen, der Netzwerk-Thread arbeitet weiter
        return info.is_published()             # True erst, wenn der Broker den Empfang bestätigt hat

    def beenden(self):                         # geordnet abmelden
        if self.verbunden.is_set():            # nur wenn wir überhaupt verbunden sind
            daten = vertrag.nachricht(self.modul, "connection_status", "offline")  # offline selbst senden, weil ein geordnetes Trennen den Last Will nicht auslöst
            info = self.client.publish(self.status_topic, vertrag.als_json(self.status_topic, daten), qos=1, retain=True)  # retained, wie online
            self.quittiert(info, 2.0)          # höchstens 2 s warten, bis der Broker sie hat
        self.client.loop_stop()                # Netzwerk-Thread beenden
        self.client.disconnect()               # Verbindung sauber schließen
