#!/usr/bin/env python3
"""SENTINEL Zutrittskontrolle: PIN am 4x4-Keypad, Sperre nach 3 Fehlversuchen.

Start:
    python3 zutritt.py               Keypad + Ampel-LEDs + Summer
    python3 zutritt.py --tastatur    PIN über die PC-Tastatur (SSH), LEDs und Summer echt
    python3 zutritt.py --tasten-test zeigt nur, welche Keypad-Taste gedrückt wird

Bedienung: Ziffern tippen, # bestätigt, * löscht die Eingabe.

Schaltung (Pi 400, Ampel aus Tag 3 bleibt gesteckt):
    Keypad Pin 1-4 (Zeilen)   GPIO5, GPIO6, GPIO13, GPIO19   = Pins 29, 31, 33, 35
    Keypad Pin 5-8 (Spalten)  GPIO26, GPIO16, GPIO20, GPIO21 = Pins 37, 36, 38, 40
    Auto rot / gelb / grün    GPIO25, GPIO8, GPIO7           = Pins 22, 24, 26
    Summer über PNP           GPIO18                         = Pin 12
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er erklärt Zweck, Start und Verkabelung.

# argparse liest die Schalter beim Start, z. B. --tastatur.
import argparse

# json verpackt die Funk-Meldung für MQTT (Übung tag05-mqtt).
import json

# os liest die Umgebungsvariable MQTT_HOST.
import os

# sys gibt Zugriff auf die Tastatur-Eingabe (sys.stdin).
import sys

# threading lässt einen Programmteil nebenher laufen. Wir nutzen das für den Sperr-Wächter.
import threading

# time liefert die Uhrzeit und sleep (warten).
import time

# Aus gpiozero holen wir die fertigen Bauteil-Klassen:
# LED für die Lampen, Buzzer für den Summer, Button für die Keypad-Spalten,
# OutputDevice für die Keypad-Zeilen (ein Pin, den wir an- und ausschalten).
from gpiozero import LED, Buzzer, Button, OutputDevice

# Unsere eigene Datenbank-Datei zutritt_db.py, hier kurz "db" genannt.
import zutritt_db as db

# paho-mqtt ist freiwillig: Ist es installiert, meldet das Keypad jeden Versuch per MQTT.
# Fehlt es, läuft alles wie vorher, nur ohne Funk.
try:
    import paho.mqtt.publish as mqtt_publish
except ImportError:
    mqtt_publish = None

# Einstellungen und Passwort für den Funk liegen bei SENTINEL Funk (Ordner tag05-mqtt, Tag 8):
# .env mit Host und Port, .env.password mit dem Passwort der Rolle "keypad".
# python-dotenv lädt sie, schon gesetzte Variablen gewinnen. Fehlt das Paket, geht es ohne Login.
try:
    from dotenv import load_dotenv
    from pathlib import Path
    FUNK_ORDNER = Path(__file__).resolve().parent.parent / "tag05-mqtt"
    load_dotenv(FUNK_ORDNER / ".env")
    load_dotenv(FUNK_ORDNER / ".env.password")
except ImportError:
    pass

# Broker für die Funk-Meldungen. Leer ("") schaltet den Funk ab (macht der Test so).
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
# Port aus .env, Standard 1883.
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
# Login der Rolle keypad. Die darf nur auf lf07/keypad/versuch senden, sonst nichts.
MQTT_LOGIN = ({"username": "keypad", "password": os.environ["MQTT_PASS_KEYPAD"]}
              if os.environ.get("MQTT_PASS_KEYPAD") else None)


# Meldet das Ergebnis eines PIN-Versuchs an Mosquitto. Die PIN selbst wird NIE gesendet.
def funk_melden(ergebnis):
    # Ohne paho-mqtt oder ohne Broker-Adresse: nichts tun.
    if mqtt_publish is None or not MQTT_HOST:
        return
    # Eine einzelne Nachricht senden (verbinden, senden, trennen in einem Schritt).
    try:
        mqtt_publish.single("lf07/keypad/versuch", json.dumps({"wert": ergebnis, "sender": "Pi-Keypad"}),
                            qos=1, hostname=MQTT_HOST, port=MQTT_PORT, auth=MQTT_LOGIN)
    # Läuft kein Broker, darf das die Zutrittskontrolle nicht stören.
    except Exception:
        pass

# ---------- Keypad ----------
# Die vier Zeilen-Leitungen (Keypad Pin 1 bis 4). Die Zahlen sind GPIO-Nummern (BCM).
ZEILEN = [5, 6, 13, 19]       # physische Pins 29, 31, 33, 35
# Die vier Spalten-Leitungen (Keypad Pin 5 bis 8).
SPALTEN = [26, 16, 20, 21]    # physische Pins 37, 36, 38, 40
# So sind die 16 Tasten auf dem Keypad angeordnet, Zeile für Zeile von links oben.
TASTEN = ["1", "2", "3", "A",
          "4", "5", "6", "B",
          "7", "8", "9", "C",
          "*", "0", "#", "D"]

# ---------- Anzeige: die Auto-Ampel aus Tag 3 ----------
# GPIO-Nummern für rote, gelbe und grüne LED und den Summer.
LED_ROT, LED_GELB, LED_GRUEN, SUMMER = 25, 8, 7, 18
# So viele Sekunden bleibt grün an, wenn die PIN stimmt ("Tür offen").
TUER_OFFEN = 3
# Nach so vielen Sekunden ohne Taste verfällt eine angefangene Eingabe.
EINGABE_TIMEOUT = 10


# Die Klasse Keypad kümmert sich nur um das Lesen der Tasten.
class Keypad:
    """Matrix-Abfrage: eine Zeile nach der anderen auf HIGH, dann Spalten lesen."""

    # __init__ läuft einmal, wenn man Keypad() aufruft. Hier werden die Pins eingerichtet.
    def __init__(self):
        # Jede Zeile wird ein Ausgang, der am Anfang aus (LOW) ist.
        self.zeilen = [OutputDevice(p, initial_value=False) for p in ZEILEN]
        # Jede Spalte wird ein Eingang. pull_up=False schaltet den internen Pull-down ein:
        # Ohne Tastendruck liest der Pin sicher LOW, nicht irgendeinen Zufallswert.
        self.spalten = [Button(p, pull_up=False) for p in SPALTEN]

    # Schaut einmal über alle 16 Tasten. Rückgabe: die gedrückte Taste oder None.
    def gedrueckt(self):
        # Alle Zeilen der Reihe nach durchgehen. z ist die Nummer (0 bis 3), zeile das Bauteil.
        for z, zeile in enumerate(self.zeilen):
            # Diese eine Zeile auf HIGH (3,3 V) schalten.
            zeile.on()
            # 1 ms warten, damit die Spannung auf der Leitung stabil ist.
            time.sleep(0.001)
            # Jetzt alle Spalten prüfen. s ist die Spaltennummer (0 bis 3).
            for s, spalte in enumerate(self.spalten):
                # Liest die Spalte HIGH, verbindet eine gedrückte Taste sie mit unserer Zeile.
                if spalte.is_pressed:
                    # Zeile wieder ausschalten, bevor wir zurückspringen.
                    zeile.off()
                    # Position in der Tastenliste: Zeile mal 4 plus Spalte. Beispiel 5: 1*4+1 = 5.
                    return TASTEN[z * 4 + s]
            # In dieser Zeile war nichts gedrückt: Zeile wieder aus, nächste Zeile.
            zeile.off()
        # Keine Taste gedrückt.
        return None

    # Liefert jede Taste genau einmal pro Druck. "yield" macht daraus einen Generator:
    # Die for-Schleife im Hauptprogramm bekommt so eine Taste nach der anderen.
    def tasten(self):
        # Merkt sich die Taste der vorigen Runde, damit ein langer Druck nur einmal zählt.
        letzte = None
        # Endlos weiter abfragen, bis das Programm beendet wird.
        while True:
            # Einmal über das ganze Keypad schauen.
            t = self.gedrueckt()
            # Neue Taste (nicht dieselbe wie eben)? Dann weitergeben.
            if t and t != letzte:
                yield t
            # Für die nächste Runde merken, was gerade gedrückt ist (oder None).
            letzte = t
            # 20 ms Pause: 50 Abfragen pro Sekunde reichen und entprellen die Taste.
            time.sleep(0.02)

    # Gibt alle Pins wieder frei.
    def close(self):
        # Zeilen und Spalten nacheinander schließen.
        for g in self.zeilen + self.spalten:
            g.close()


# Die Klasse Anzeige steuert LEDs und Summer.
class Anzeige:
    # Einrichten der drei LEDs und des Summers.
    def __init__(self):
        # Drei LEDs an den GPIO-Nummern von oben.
        self.rot, self.gelb, self.gruen = LED(LED_ROT), LED(LED_GELB), LED(LED_GRUEN)
        # Summer über den PNP-Transistor: active_high=False, denn der PNP schaltet bei LOW durch.
        self.summer = Buzzer(SUMMER, active_high=False)
        # Ein Schloss (Lock): Nur ein Programmteil darf gleichzeitig die LEDs steuern.
        # Sonst würde der Sperr-Wächter mitten in ein Blinksignal funken.
        self.sperre = threading.Lock()

    # Kurzes Signal bei jedem Tastendruck.
    def klick(self):
        # Gelb blinkt einmal kurz (0,06 s an). Läuft im Hintergrund weiter.
        self.gelb.blink(0.06, 0, n=1)
        # Summer tickt einmal ganz kurz (0,03 s).
        self.summer.beep(0.03, 0, n=1)

    # Signal "richtige PIN, Tür offen".
    def offen(self):
        # Schloss nehmen, damit niemand dazwischenfunkt.
        with self.sperre:
            # Rot sicher aus.
            self.rot.off()
            # Zwei kurze Pieptöne (Hintergrund).
            self.summer.beep(0.08, 0.08, n=2)
            # Grün an.
            self.gruen.on()
            # Grün bleibt TUER_OFFEN Sekunden an.
            time.sleep(TUER_OFFEN)
            # Grün wieder aus.
            self.gruen.off()

    # Signal "falsche PIN".
    def falsch(self):
        # Schloss nehmen.
        with self.sperre:
            # Ein langer Ton (0,5 s).
            self.summer.beep(0.5, 0, n=1)
            # Rot blinkt dreimal. background=False: erst weitermachen, wenn das Blinken fertig ist.
            self.rot.blink(0.15, 0.15, n=3, background=False)

    # Signal "dritter Fehler, jetzt gesperrt".
    def alarm(self):
        # Schloss nehmen.
        with self.sperre:
            # Vier Alarmtöne.
            self.summer.beep(0.3, 0.2, n=4)
            # Rot blinkt zehnmal schnell (dauert 2 s).
            self.rot.blink(0.1, 0.1, n=10, background=False)
            # Danach bleibt Rot dauerhaft an, solange gesperrt ist.
            self.rot.on()

    # Gibt alle Pins frei, LEDs und Summer gehen dabei aus.
    def close(self):
        for g in (self.rot, self.gelb, self.gruen, self.summer):
            g.close()


# Die Klasse Zutritt ist die eigentliche Logik. Sie kennt keine Pins,
# nur Tasten rein und Signale raus. Deshalb lässt sie sich ohne Hardware testen.
class Zutritt:
    # Merkt sich Anzeige, Datenbank-Verbindung und wohin Meldungen geschrieben werden.
    def __init__(self, anzeige, con, ausgabe=print):
        self.anzeige, self.con, self.ausgabe = anzeige, con, ausgabe
        # Die bisher getippten Ziffern.
        self.eingabe = ""
        # Zeitpunkt der letzten Taste (für den 10-Sekunden-Timeout).
        self.letzte_taste = 0.0

    # Wird für jede gedrückte Taste einmal aufgerufen.
    def taste(self, t):
        # Zuerst in der Datenbank nachsehen, ob gerade gesperrt ist.
        st = db.status(self.con)
        # Gesperrt?
        if st["gesperrt"]:
            # Meldung mit Restzeit, gerundet auf ganze Sekunden.
            self.ausgabe(f"Gesperrt, noch {st['rest']:.0f} s. Taste ignoriert.")
            # Rot sicher an.
            self.anzeige.rot.on()
            # Taste nicht weiter beachten.
            return "gesperrt"
        # War die letzte Taste länger als 10 s her? Dann alte Eingabe verwerfen.
        if time.time() - self.letzte_taste > EINGABE_TIMEOUT:
            self.eingabe = ""
        # Zeitpunkt dieser Taste merken.
        self.letzte_taste = time.time()
        # Kurzes Klick-Signal (gelb + Ticken).
        self.anzeige.klick()
        # Stern = Eingabe löschen.
        if t == "*":
            self.eingabe = ""
            self.ausgabe("Eingabe gelöscht")
            return "geloescht"
        # Raute = PIN abschicken.
        if t == "#":
            return self.bestaetigen()
        # Ziffer und noch Platz (höchstens 8 Stellen)? Dann anhängen.
        if t.isdigit() and len(self.eingabe) < 8:
            self.eingabe += t
            # Nur Sternchen zeigen, nie die PIN selbst.
            self.ausgabe("PIN: " + "*" * len(self.eingabe))
        # A bis D tun nichts. Die Eingabe läuft einfach weiter.
        return "eingabe"

    # Prüft die getippte PIN und reagiert darauf.
    def bestaetigen(self):
        # PIN übernehmen und das Eingabefeld gleich wieder leeren.
        pin, self.eingabe = self.eingabe, ""
        # PIN gegen die Datenbank prüfen. Leere Eingabe zählt als falsch.
        benutzer = db.pin_pruefen(self.con, pin) if pin else None
        # Versuch speichern. Die Datenbank sagt uns: "ok", "falsch" oder "gesperrt".
        ergebnis = db.versuch_eintragen(self.con, benutzer is not None, benutzer)
        # Ergebnis zusätzlich per MQTT melden (ok / falsch / gesperrt).
        funk_melden(ergebnis)
        # Richtige PIN.
        if ergebnis == "ok":
            self.ausgabe(f"Zutritt für {benutzer['name']}")
            self.anzeige.offen()
        # Falsche PIN, aber noch nicht gesperrt.
        elif ergebnis == "falsch":
            st = db.status(self.con)
            self.ausgabe(f"Falsche PIN ({st['fehlversuche']} von {db.MAX_FEHLVERSUCHE})")
            self.anzeige.falsch()
        # Dritter Fehler: Sperre.
        else:
            st = db.status(self.con)
            self.ausgabe(f"3 Fehlversuche: GESPERRT für {st['rest']:.0f} s")
            self.anzeige.alarm()
        # Ergebnis zurückgeben (wichtig für den Test).
        return ergebnis


# Läuft nebenher: hält Rot an, solange gesperrt ist, und schaltet es danach aus.
# Merkt so auch, wenn ein Admin im Dashboard entsperrt.
def sperr_waechter(anzeige, stopp):
    # Eigene Datenbank-Verbindung, denn SQLite-Verbindungen sollen nicht zwischen Threads wandern.
    con = db.verbinden()
    # Zustand der letzten Runde. None heißt: noch nicht bekannt.
    war_gesperrt = None
    # Laufen, bis das Hauptprogramm "stopp" setzt.
    while not stopp.is_set():
        # Aktuell gesperrt?
        gesperrt = db.status(con)["gesperrt"]
        # Nur reagieren, wenn sich etwas geändert hat.
        if gesperrt != war_gesperrt:
            # Schloss nehmen, damit kein Blinksignal gestört wird.
            with anzeige.sperre:
                # Rot an bei Sperre, aus ohne Sperre.
                anzeige.rot.value = gesperrt
            # Sperre ist gerade zu Ende gegangen? Dann Bescheid geben.
            if war_gesperrt and not gesperrt:
                print("Sperre aufgehoben, Eingabe wieder möglich")
            # Neuen Zustand merken.
            war_gesperrt = gesperrt
        # Eine halbe Sekunde warten (oder sofort aufhören, wenn stopp gesetzt wird).
        stopp.wait(0.5)


# Ersatz für das Keypad: die Tastatur wird zum Keypad (Pi-400-Tastatur oder Notebook über SSH).
# Jede Taste wirkt sofort, ohne Enter. Enter zählt als #, Rücktaste als *.
def tastatur_tasten():
    # Kurze Bedienhilfe ausgeben.
    print("Tastatur-Modus: Ziffern tippen, Enter oder # bestätigt, Rücktaste oder * löscht. Strg+C beendet.")
    # Läuft das Programm nicht in einem echten Terminal (z. B. Eingabe aus einer Datei)?
    if not sys.stdin.isatty():
        # Dann einfach Zeile für Zeile lesen.
        for zeile in sys.stdin:
            # Kleinbuchstaben groß machen und Zeichen für Zeichen weitergeben.
            for t in zeile.strip().upper():
                # Nur Zeichen, die es auf dem Keypad auch gibt.
                if t in TASTEN:
                    yield t
        return
    # termios und tty gibt es nur unter Linux. Sie schalten das Terminal um.
    import termios
    import tty
    # Die Nummer des Tastatur-Eingangs.
    fd = sys.stdin.fileno()
    # Aktuelle Terminal-Einstellungen sichern, um sie am Ende wiederherzustellen.
    alt = termios.tcgetattr(fd)
    try:
        # cbreak-Modus: jede Taste kommt sofort an, ohne auf Enter zu warten. Strg+C geht weiter.
        tty.setcbreak(fd)
        # Endlos Tasten lesen.
        while True:
            # Genau ein Zeichen lesen.
            c = sys.stdin.read(1)
            # Enter wirkt wie die Raute.
            if c in "\r\n":
                c = "#"
            # Rücktaste (Backspace) wirkt wie der Stern.
            elif c in "\x7f\x08":
                c = "*"
            # Kleinbuchstaben groß machen (a wird A).
            c = c.upper()
            # Nur Keypad-Zeichen weitergeben, alles andere ignorieren.
            if c in TASTEN:
                yield c
    finally:
        # Terminal wieder normal einstellen, sonst bleibt die SSH-Sitzung "komisch".
        termios.tcsetattr(fd, termios.TCSADRAIN, alt)


# Das Hauptprogramm.
def main():
    # Startschalter festlegen. Der Docstring oben dient als Hilfetext (python3 zutritt.py -h).
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Schalter --tastatur: PC-Tastatur statt Keypad.
    p.add_argument("--tastatur", action="store_true", help="PIN über die Tastatur statt Keypad")
    # Schalter --tasten-test: nur Tasten anzeigen.
    p.add_argument("--tasten-test", action="store_true", help="nur Keypad-Tasten anzeigen")
    # Die Schalter auswerten.
    a = p.parse_args()

    # Modus Tasten-Test: Verkabelung prüfen, ohne Datenbank und ohne LEDs.
    if a.tasten_test:
        # Keypad einrichten.
        kp = Keypad()
        print("Drück Tasten auf dem Keypad, Strg+C beendet.")
        # try/finally: Pins werden auf jeden Fall freigegeben, auch bei Strg+C.
        try:
            # Jede gedrückte Taste anzeigen.
            for t in kp.tasten():
                print("Taste:", t)
        # Strg+C beendet die Schleife ohne Fehlermeldung.
        except KeyboardInterrupt:
            pass
        # Am Ende die Pins freigeben.
        finally:
            kp.close()
        # Fertig, der Rest von main() wird übersprungen.
        return

    # Datenbank öffnen (legt sie beim ersten Mal an).
    con = db.verbinden()
    # Gibt es schon mindestens einen Benutzer? Ohne Benutzer könnte niemand rein.
    if not con.execute("SELECT 1 FROM benutzer").fetchone():
        print("Noch keine Benutzer. Erst anlegen: python3 verwalten.py neu <name>")
        return
    # LEDs und Summer einrichten.
    anzeige = Anzeige()
    # Keypad nur einrichten, wenn nicht im Tastatur-Modus.
    kp = None if a.tastatur else Keypad()
    # Ein Event als Stopp-Signal für den Sperr-Wächter.
    stopp = threading.Event()
    # Den Sperr-Wächter als Hintergrund-Thread starten. daemon=True: endet mit dem Programm.
    threading.Thread(target=sperr_waechter, args=(anzeige, stopp), daemon=True).start()
    # Die Logik anlegen.
    zutritt = Zutritt(anzeige, con)
    print("SENTINEL Zutrittskontrolle bereit.")
    # Hauptschleife, abgesichert mit try/finally.
    try:
        # Tasten kommen je nach Modus von der Tastatur oder vom Keypad.
        for t in (tastatur_tasten() if a.tastatur else kp.tasten()):
            # Jede Taste an die Logik geben.
            zutritt.taste(t)
    # Strg+C: sauber beenden.
    except KeyboardInterrupt:
        print("\nBeendet.")
    # Aufräumen: Wächter stoppen, LEDs aus, Pins freigeben.
    finally:
        stopp.set()
        anzeige.close()
        if kp:
            kp.close()


# Nur wenn die Datei direkt gestartet wird (nicht beim Import im Test), main() ausführen.
if __name__ == "__main__":
    main()
