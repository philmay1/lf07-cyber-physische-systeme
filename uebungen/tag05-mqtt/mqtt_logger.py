#!/usr/bin/env python3
"""MQTT-Logger: abonniert lf07/# bei Mosquitto und schreibt jedes Event in mqtt.db.

Das ist der Kern der Aufgabe: Eine Funktion macht eine Subscription auf das Topic
und schreibt Wert und Zeit in eine Datenbank.

Start auf dem Pi:
    python3 mqtt_logger.py          mitschreiben, Strg+C beendet
    python3 mqtt_logger.py --neu    vorher alle alten Events löschen
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er erklärt Zweck und Start.

# argparse liest die Schalter beim Start, z. B. --neu.
import argparse

# time macht aus der Empfangszeit eine Uhrzeit für die Ausgabe.
import time

# Unsere gemeinsame Datei mit Datenbank und MQTT-Client, hier kurz "fdb".
import funk_db as fdb


# Wird aufgerufen, sobald die Verbindung zum Broker steht (auch nach jedem Neuverbinden).
# properties=None: paho 2.x schickt ein Argument mehr als paho 1.x.
def verbunden(client, userdata, flags, rc, properties=None):
    # rc 0 heißt: Broker hat die Verbindung angenommen.
    if rc == 0:
        # Das Abo hier anlegen, damit es nach einem Neuverbinden automatisch wieder da ist.
        # qos=1: Der Broker liefert jede Nachricht mindestens einmal.
        client.subscribe(fdb.THEMA, qos=1)
        print(f"Verbunden mit {fdb.MQTT_HOST}, abonniert: {fdb.THEMA}")
    # Sonst war etwas falsch (z. B. Broker lehnt ab).
    else:
        print("Broker lehnt die Verbindung ab, Code", rc)


# DIE Funktion aus der Aufgabe: läuft für jede Nachricht auf lf07/# einmal.
def beim_empfang(client, userdata, msg):
    # Empfangszeit festhalten (Sekunden seit 1970, mit Nachkommastellen).
    zeit = time.time()
    # Aus den Bytes Wert und Sender machen (PINs werden dabei unkenntlich).
    wert, sender = fdb.payload_lesen(msg.topic, msg.payload)
    # In die Datenbank schreiben. userdata ist unsere Datenbank-Verbindung (siehe unten).
    nr = fdb.event_speichern(userdata, msg.topic, wert, sender, zeit)
    # Kurze Zeile im Terminal, damit man live sieht, was ankommt.
    print(f"#{nr:<4} {time.strftime('%H:%M:%S', time.localtime(zeit))}  "
          f"{msg.topic:<32} {sender:<14} {wert}")


# Das Hauptprogramm.
def main():
    # Schalter festlegen. Der Docstring dient als Hilfetext (python3 mqtt_logger.py -h).
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # --neu: Tabelle vor dem Start leeren.
    p.add_argument("--neu", action="store_true", help="alle alten Events löschen")
    # Die Schalter auswerten.
    a = p.parse_args()

    # Datenbank öffnen (legt mqtt.db beim ersten Mal an).
    con = fdb.verbinden()
    # Auf Wunsch frisch anfangen.
    if a.neu:
        fdb.leeren(con)
        print("Alte Events gelöscht.")
    print(f"Datenbank: {fdb.DB_DATEI}  ({fdb.anzahl(con)} Events drin)")

    # MQTT-Client anlegen.
    client = fdb.client_bauen("logger")
    # Die Datenbank-Verbindung als userdata mitgeben. Sie landet in beim_empfang().
    client.user_data_set(con)
    # Unsere Funktionen als Rückrufe eintragen.
    client.on_connect = verbunden
    client.on_message = beim_empfang
    # Mit dem Broker verbinden. 1883 ist der MQTT-Standardport, 30 s Lebenszeichen-Abstand.
    client.connect(fdb.MQTT_HOST, 1883, keepalive=30)
    # Endlos auf Nachrichten warten. Bricht die Verbindung ab, verbindet paho selbst neu.
    try:
        client.loop_forever()
    # Strg+C: sauber beenden.
    except KeyboardInterrupt:
        print(f"\nBeendet. {fdb.anzahl(con)} Events in der Datenbank.")
        client.disconnect()


# Nur beim direkten Start ausführen, nicht beim Import im Test.
if __name__ == "__main__":
    main()
