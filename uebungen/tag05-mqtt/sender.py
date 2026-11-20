#!/usr/bin/env python3
"""MQTT-Sender: schickt Events an Mosquitto. Läuft auf dem Pi und auf dem Notebook.

Braucht nur paho-mqtt (Notebook: pip install paho-mqtt).

    python sender.py --anzahl 20                 20 Messwerte (Raumklima, simuliert) senden
    python sender.py --cpu --anzahl 20           20 echte Messwerte: CPU-Temperatur des Pi
    python sender.py --text "Hallo Klasse"       eine Nachricht senden
    python sender.py                             tippen, jede Zeile ist ein Event
    python sender.py --host 192.168.2.117 ...    anderer Broker (Standard: raspberrypi.local)
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er dient als Hilfetext (python sender.py -h).

# argparse liest die Schalter beim Start, z. B. --anzahl 20.
import argparse

# json verpackt Wert und Sender als {"wert": ..., "sender": ...}.
import json

# os liest die Umgebungsvariable MQTT_HOST.
import os

# random erzeugt die simulierten Messwerte und eine Zufallszahl für den Client-Namen.
import random

# socket liefert den Rechnernamen, der als Absender dient.
import socket

# time wartet zwischen zwei Events.
import time

# paho-mqtt ist die MQTT-Bibliothek. Fehlt sie, sagen wir, wie man sie installiert.
try:
    import paho.mqtt.client as mqtt
except ImportError:
    raise SystemExit("paho-mqtt fehlt. Installieren mit:  pip install paho-mqtt")

# Hier steht auf dem Pi die CPU-Temperatur in Tausendstel Grad.
CPU_DATEI = "/sys/class/thermal/thermal_zone0/temp"


# Baut einen MQTT-Client, der mit paho-mqtt 1.x und 2.x läuft.
def client_bauen(name):
    # Eindeutiger Client-Name, z. B. "sender-NOTEBOOK-1234".
    client_id = f"sender-{name}-{random.randint(1000, 9999)}"
    # paho 2.x braucht die Angabe der Rückruf-Version ...
    try:
        return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    # ... paho 1.x kennt sie nicht.
    except AttributeError:
        return mqtt.Client(client_id=client_id)


# Schickt ein Event und wartet, bis der Broker es bestätigt hat.
def senden(client, topic, wert, name):
    # Wert und Absender als JSON-Text verpacken.
    nachricht = json.dumps({"wert": wert, "sender": name})
    # qos=1: Der Broker bestätigt den Empfang (PUBACK). Ohne Bestätigung sendet paho erneut.
    info = client.publish(topic, nachricht, qos=1)
    # Warten, bis die Bestätigung da ist (paho 2.x: höchstens 5 s).
    try:
        info.wait_for_publish(timeout=5)
    # paho 1.x (Pi) kennt timeout noch nicht und wartet einfach.
    except TypeError:
        info.wait_for_publish()
    # Zeile im Terminal: Uhrzeit, Topic, Wert.
    print(f"{time.strftime('%H:%M:%S')}  gesendet  {topic:<30} {wert}")


# Liest die echte CPU-Temperatur des Pi in Grad Celsius.
def cpu_temperatur():
    # Datei öffnen, Zahl lesen, durch 1000 teilen, auf eine Nachkommastelle runden.
    with open(CPU_DATEI) as f:
        return round(int(f.read()) / 1000, 1)


# Das Hauptprogramm.
def main():
    # Schalter festlegen. Der Docstring oben ist der Hilfetext.
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Adresse des Brokers. Standard: Umgebungsvariable MQTT_HOST oder der Pi im Netz.
    p.add_argument("--host", default=os.environ.get("MQTT_HOST", "raspberrypi.local"))
    # Absendername. Standard: Name des Rechners, ohne Sonderzeichen, höchstens 16 Zeichen.
    p.add_argument("--name", default="".join(c for c in socket.gethostname() if c.isalnum())[:16])
    # Wie viele Messwerte gesendet werden.
    p.add_argument("--anzahl", type=int, default=0, help="so viele Messwerte senden")
    # Abstand zwischen zwei Messwerten in Sekunden.
    p.add_argument("--abstand", type=float, default=0.7, help="Sekunden zwischen zwei Werten")
    # Echte CPU-Temperatur statt simulierter Werte (nur auf dem Pi).
    p.add_argument("--cpu", action="store_true", help="CPU-Temperatur des Pi senden")
    # Eine einzelne Textnachricht senden.
    p.add_argument("--text", help="eine Nachricht senden")
    # Die Schalter auswerten.
    a = p.parse_args()

    # Client bauen und verbinden.
    client = client_bauen(a.name)
    # Verbindung herstellen. Klappt es nicht, einen verständlichen Hinweis geben.
    try:
        client.connect(a.host, 1883, keepalive=30)
    except OSError as fehler:
        raise SystemExit(f"Kein Broker unter {a.host} erreichbar ({fehler}).\n"
                         "Tipp: IP des Pi angeben, z. B.  --host 192.168.2.117")
    # Netzwerk-Schleife im Hintergrund starten. Sie erledigt Senden und Bestätigungen.
    client.loop_start()
    print(f"Verbunden mit {a.host} als {a.name}")

    # try/finally: am Ende auf jeden Fall sauber trennen.
    try:
        # Fall 1: eine einzelne Nachricht.
        if a.text:
            senden(client, f"lf07/{a.name}/text", a.text, a.name)
        # Fall 2: echte CPU-Temperatur, so oft wie --anzahl sagt (mindestens 1).
        elif a.cpu:
            for _ in range(max(a.anzahl, 1)):
                senden(client, "lf07/pi/cpu_temperatur", cpu_temperatur(), "Pi-Sensor")
                time.sleep(a.abstand)
        # Fall 3: simulierte Messreihe "Raumklima". Die Temperatur schwankt leicht.
        elif a.anzahl:
            temperatur = 21.0
            for i in range(1, a.anzahl + 1):
                # Zufällig ein bisschen hoch oder runter, auf eine Nachkommastelle gerundet.
                temperatur = round(temperatur + random.uniform(-0.3, 0.3), 1)
                senden(client, f"lf07/{a.name}/temperatur", temperatur, a.name)
                time.sleep(a.abstand)
        # Fall 4: frei tippen. Jede Zeile wird ein Event, leere Zeile beendet.
        else:
            print("Text tippen und Enter drücken. Leere Zeile beendet.")
            while True:
                zeile = input("> ").strip()
                if not zeile:
                    break
                senden(client, f"lf07/{a.name}/text", zeile, a.name)
    # Strg+C beendet ohne Fehlermeldung.
    except KeyboardInterrupt:
        print()
    # Aufräumen: Verbindung trennen und Netzwerk-Schleife stoppen.
    finally:
        client.disconnect()
        client.loop_stop()


# Nur beim direkten Start ausführen.
if __name__ == "__main__":
    main()
