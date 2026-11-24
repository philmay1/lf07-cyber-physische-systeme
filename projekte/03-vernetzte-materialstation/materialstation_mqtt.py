"""SENTINEL Projekt 03: Vernetzte Materialstation (Tag 3, AB4).

Jeder Tastendruck wird eine Materialanforderung nach dem Schnittstellenvertrag 1.0.0
und geht per MQTT an sentinel/lab01/material/station01/request (QoS 1, nicht retained).
Das Status-Topic meldet online/offline, offline auch als Last Will.

Ablauf laut Arbeitsblatt: GPIO-Callback -> Warteschlange -> Sende-Thread -> Vertrag prüfen -> publish.
Der Callback selbst sendet nie, damit ein langsames Netz den Taster nicht blockiert.

LED-Muster: grün Doppelblitz = verbunden, grün an = wird gesendet, grün zwei Blitze = Broker hat
quittiert, rot langsam blinkend = keine Verbindung. Beenden mit Strg+C.
"""
import queue                                   # Warteschlange zwischen Taster-Callback und Sende-Thread
import sys                                     # Suchpfad
import threading                               # eigener Sende-Thread
import time                                    # Pausen
from pathlib import Path                       # Pfade

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gemeinsam"))  # projekte/gemeinsam importierbar machen

from gpiozero import LED, Button               # noqa: E402  Taster und LEDs

import pinplan                                 # noqa: E402  zentrale Pinbelegung
import vertrag                                 # noqa: E402  Payload nach Katalog bauen
from mqtt_verbindung import Modul              # noqa: E402  Verbindung mit Last Will und Status

ENDE = object()                                # besonderes Objekt, das dem Sende-Thread "aufhören" sagt


class Materialstation:                         # alles, was die Station braucht, an einem Ort
    def __init__(self):                        # Geräte und Verbindung anlegen
        self.taster = Button(pinplan.TASTER, pull_up=True, bounce_time=0.05)  # Pull-up und Entprellen
        self.gruen = LED(pinplan.LED_GRUEN)    # Status-LED für Senden und Quittung
        self.rot = LED(pinplan.LED_ROT)        # Fehler-LED für Verbindungsprobleme
        self.mqtt = Modul("material", "sentinel-station01")  # Modul "material", eindeutiger Client-Name
        self.warteschlange = queue.Queue(maxsize=50)  # begrenzt: bei Netzausfall läuft der Speicher nicht voll
        self.gesendet = 0                      # Zähler quittierter Anforderungen
        self.fehler = 0                        # Zähler nicht zugestellter Anforderungen
        self.taster.when_pressed = self.gedrueckt  # Callback verbinden

    def gedrueckt(self):                       # Callback: läuft im gpiozero-Thread, muss schnell sein
        try:                                   # die Warteschlange könnte voll sein
            self.warteschlange.put_nowait(time.monotonic())  # nur den Zeitpunkt ablegen, nicht senden
        except queue.Full:                     # 50 Anforderungen stehen schon an
            print("Warteschlange voll, Druck verworfen")  # ehrlich melden statt still verlieren

    def sende_schleife(self):                  # läuft im eigenen Thread und arbeitet die Warteschlange ab
        while True:                            # bis ENDE kommt
            eintrag = self.warteschlange.get() # blockiert, bis etwas in der Schlange liegt
            if eintrag is ENDE:                # Signal zum Aufhören
                return                         # Thread beenden
            daten = vertrag.nachricht("material", "material_request", "active", request_count=1)  # Vertrag 3.5 + 3.6
            self.rot.off()                     # ein neuer Versuch beginnt, alte Fehleranzeige aus
            self.gruen.on()                    # "senden": LED an
            info = self.mqtt.senden("request", daten)  # prüfen und an den Broker geben
            ok = self.mqtt.quittiert(info, 3.0)  # bis zu 3 s auf PUBACK warten
            self.gruen.off()                   # Senden ist vorbei
            if ok:                             # Broker hat bestätigt
                self.gesendet += 1             # zählen
                print(f"Anforderung {self.gesendet} gesendet, message_id {daten['message_id']}")  # Nachweis mit ID
                self.gruen.blink(0.1, 0.1, n=2, background=True)  # zwei kurze Blitze = quittiert
            else:                              # keine Bestätigung
                self.fehler += 1               # zählen
                print("Anforderung NICHT zugestellt (keine Verbindung oder keine Quittung)")  # keine Erfolgsmeldung vortäuschen
                self.rot.blink(1, 1, background=True)  # langsames Fehlerblinken

    def starten(self):                         # Verbindung aufbauen und Sende-Thread starten
        if self.mqtt.starten(5.0):             # bis zu 5 s auf den Broker warten
            print("Mit Broker verbunden.")     # Erfolg melden
            self.gruen.blink(0.1, 0.1, n=2, background=True)  # Doppelblitz = bereit
        else:                                  # Broker nicht erreichbar
            print("Broker nicht erreichbar, paho versucht es im Hintergrund weiter.")  # lokal läuft alles weiter
            self.rot.blink(1, 1, background=True)  # langsames Fehlerblinken
        self.thread = threading.Thread(target=self.sende_schleife, daemon=True)  # daemon: stirbt mit dem Programm
        self.thread.start()                    # Sende-Thread loslaufen lassen

    def beenden(self):                         # geordnet herunterfahren, Reihenfolge laut Arbeitsblatt
        self.taster.when_pressed = None        # keine neuen Drücke mehr annehmen
        self.warteschlange.put(ENDE)           # Sende-Thread nach dem letzten Eintrag beenden
        self.thread.join(timeout=5)            # höchstens 5 s warten
        self.mqtt.beenden()                    # offline melden, Loop stoppen, trennen
        for geraet in (self.gruen, self.rot):  # beide LEDs
            geraet.off()                       # aus
            geraet.close()                     # Pin freigeben
        self.taster.close()                    # Taster-Pin freigeben


def main():                                    # Hauptprogramm
    station = Materialstation()                # alles anlegen
    station.starten()                          # verbinden und Sende-Thread starten
    print("Materialstation bereit. Taster drücken, Strg+C beendet.")  # Startmeldung
    try:                                       # geschützter Block
        while True:                            # Hauptthread hat nichts zu tun ...
            time.sleep(1)                      # ... und schläft, die Arbeit machen Callback und Sende-Thread
    except KeyboardInterrupt:                  # Strg+C
        print(f"\nBeendet. Gesendet: {station.gesendet}, nicht zugestellt: {station.fehler}")  # Bilanz
    finally:                                   # Aufräumen in jedem Fall
        station.beenden()                      # geordnetes Ende


if __name__ == "__main__":                     # nur beim direkten Start
    main()                                     # los geht's
