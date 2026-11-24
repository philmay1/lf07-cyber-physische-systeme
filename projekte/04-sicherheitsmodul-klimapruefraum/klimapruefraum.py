"""SENTINEL Projekt 04: Sicherheitsmodul Klimaprüfraum (Tag 4, AB3).

Bewegt sich im Prüfraum 15 Sekunden lang niemand, könnte eine Person bewusstlos sein.
Dann sendet das Modul genau EINEN Alarm per MQTT (sentinel/lab01/safety/chamber01/alarm).
Die letzten 9 Sekunden laufen als Countdown im Terminal, die gelbe LED blinkt dazu.
Jede Bewegung bricht den Countdown sofort ab und schaltet nach einem Alarm wieder scharf.

Bewegung kommt von einem PIR-Melder an GPIO17 (Pin 11) oder, ohne PIR, vom Taster an
GPIO27 (Pin 13): Aufruf mit --taster. Jeder Druck zählt dann als Bewegung.
Alle Zeiten laufen über time.monotonic(), damit eine Uhrzeitkorrektur nichts verfälscht.

Grenze: Das ist ein Lern-Demonstrator, kein zugelassenes Sicherheitssystem.
"""
import argparse                                # Kommandozeilen-Option --taster
import sys                                     # Suchpfad
import time                                    # monotone Zeit und Pausen
from pathlib import Path                       # Pfade

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "gemeinsam"))  # projekte/gemeinsam importierbar machen

import vertrag                                 # noqa: E402  Alarm-Payload nach Katalog

SCHWELLE_S = 15                                # so lange ohne Bewegung bis zum Alarm (Arbeitsblatt 6.3)
COUNTDOWN_S = 9                                # einstellige Anzeige: die letzten 9 s werden heruntergezählt
DAUER_HIGH_S = 120                             # länger ununterbrochen "Bewegung" ist unplausibel (Sensorfehler)

UEBERWACHUNG, COUNTDOWN, ALARMIERT, FEHLER = "Überwachung", "Countdown", "Alarmiert", "Sensorfehler"  # die vier Zustände


class Raumwaechter:                            # reine Zustandslogik, ohne GPIO und ohne Netz: so ist sie testbar
    def __init__(self, jetzt, alarm_senden):   # jetzt = Startzeit, alarm_senden = Funktion, die den Alarm verschickt
        self.zustand = UEBERWACHUNG            # Startzustand laut Zustandsmodell 6.4
        self.letzte_bewegung = jetzt           # Startzeit zählt wie eine Bewegung (definierter Start)
        self.high_seit = None                  # seit wann der Sensor ununterbrochen Bewegung meldet
        self.alarm_gesendet = False            # Einmal-Alarm-Flag: pro Vorfall nur ein Alarm
        self.alarm_senden = alarm_senden       # wird beim Alarm aufgerufen
        self.alarme = 0                        # Anzahl gesendeter Alarme (für Anzeige und Test)

    def schritt(self, jetzt, bewegung):        # wird alle 20-50 ms mit der aktuellen Zeit und dem Sensorwert aufgerufen
        if bewegung:                           # Sensor meldet Bewegung
            self.high_seit = self.high_seit if self.high_seit is not None else jetzt  # Beginn der HIGH-Phase merken
            if jetzt - self.high_seit > DAUER_HIGH_S:  # viel zu lange ununterbrochen HIGH?
                self.zustand = FEHLER          # Diagnosezustand, kein falscher Countdown
                return self.zustand            # nichts weiter tun
            self.letzte_bewegung = jetzt       # Zeit aktualisieren
            self.alarm_gesendet = False        # Wieder-Scharfschaltung: neuer Vorfall möglich
            self.zustand = UEBERWACHUNG        # zurück in die Überwachung, Countdown ist damit abgebrochen
            return self.zustand                # fertig für diesen Schritt
        self.high_seit = None                  # keine Bewegung: HIGH-Phase ist vorbei
        if self.zustand == FEHLER:             # nach einem Sensorfehler wieder normal weiter
            self.zustand = UEBERWACHUNG        # sobald der Sensor wieder LOW liefert
        still = jetzt - self.letzte_bewegung   # monotone Differenz: wie lange schon keine Bewegung
        if still >= SCHWELLE_S:                # Schwelle erreicht
            if not self.alarm_gesendet:        # nur beim ersten Mal in diesem Vorfall
                self.alarm_gesendet = True     # Flag zuerst setzen: auch bei Sendefehler kein Alarm-Sturm
                self.alarme += 1               # zählen
                self.alarm_senden(still)       # Alarm verschicken
            self.zustand = ALARMIERT           # bleibt alarmiert, bis sich wieder jemand bewegt
        elif still >= SCHWELLE_S - COUNTDOWN_S:  # in den letzten 9 Sekunden
            self.zustand = COUNTDOWN           # Countdown anzeigen
        else:                                  # noch weit weg von der Schwelle
            self.zustand = UEBERWACHUNG        # normale Überwachung
        return self.zustand                    # neuen Zustand zurückgeben

    def rest(self, jetzt):                     # verbleibende ganze Sekunden bis zum Alarm, für die Anzeige
        return max(0, int(SCHWELLE_S - (jetzt - self.letzte_bewegung) + 0.999))  # aufrunden: 8,3 s Rest zeigt 9


def main():                                    # Hardware- und Netzwerkteil
    parser = argparse.ArgumentParser(description="SENTINEL Klimaprüfraum")  # Optionen beschreiben
    parser.add_argument("--taster", action="store_true", help="Taster an GPIO27 statt PIR als Bewegung")  # Ersatz ohne PIR
    args = parser.parse_args()                 # Optionen lesen

    from gpiozero import LED, Button, MotionSensor  # erst hier importieren, damit der Test ohne GPIO läuft

    import pinplan                             # zentrale Pinbelegung
    from mqtt_verbindung import Modul          # MQTT mit Last Will

    if args.taster:                            # ohne PIR
        sensor = Button(pinplan.TASTER, pull_up=True)  # gedrückt = Bewegung
        bewegt = lambda: sensor.is_pressed     # noqa: E731  einheitliche Abfrage-Funktion
    else:                                      # mit PIR
        sensor = MotionSensor(pinplan.BEWEGUNGSMELDER)  # PIR liefert HIGH bei Bewegung
        bewegt = lambda: sensor.motion_detected  # noqa: E731  einheitliche Abfrage-Funktion
    gelb, rot = LED(pinplan.LED_GELB), LED(pinplan.LED_ROT)  # Countdown- und Alarm-LED
    mqtt = Modul("safety", "sentinel-chamber01")  # Modul Personensicherheit

    def alarm_senden(still):                   # wird von der Zustandslogik genau einmal pro Vorfall aufgerufen
        daten = vertrag.nachricht("safety", "inactivity_alarm", "alarm", motion_detected=False,  # Alarm-Payload, geht in der nächsten Zeile weiter
                                  alarm_type="no_motion_timeout", threshold_s=SCHWELLE_S)  # Payload wie im Arbeitsblatt 7.1
        ok = mqtt.quittiert(mqtt.senden("alarm", daten), 3.0)  # senden und auf PUBACK warten
        print(f"\nALARM: {still:.1f} s keine Bewegung. MQTT {'quittiert' if ok else 'NICHT zugestellt'}, message_id {daten['message_id']}")  # ehrlich melden

    waechter = Raumwaechter(time.monotonic(), alarm_senden)  # Zustandslogik starten
    if mqtt.starten(5.0):                      # mit dem Broker verbinden
        mqtt.status("normal", "chamber_status")  # retained Status: Überwachung läuft
    else:                                      # Broker fehlt
        print("Broker nicht erreichbar: lokale Überwachung läuft trotzdem weiter.")  # Vertrag: lokal weiterarbeiten
    print(f"Klimaprüfraum überwacht ({'Taster' if args.taster else 'PIR'}). Alarm nach {SCHWELLE_S} s ohne Bewegung. Strg+C beendet.")  # Start
    vorher = None                              # letzter angezeigter Zustand, damit nicht jede Runde gedruckt wird
    try:                                       # geschützter Block
        while True:                            # Hauptschleife
            jetzt = time.monotonic()           # aktuelle monotone Zeit
            zustand = waechter.schritt(jetzt, bewegt())  # Sensor lesen und Logik weiterschalten
            if zustand == COUNTDOWN:           # Countdown sichtbar machen
                print(f"\rCountdown: {waechter.rest(jetzt)} ", end="", flush=True)  # gleiche Zeile überschreiben
                gelb.value = int(jetzt * 2) % 2  # gelb blinkt im Halbsekundentakt
            else:                              # kein Countdown
                gelb.off()                     # gelb aus
            rot.value = zustand in (ALARMIERT, FEHLER)  # rot an bei Alarm oder Sensorfehler
            if zustand != vorher and zustand != COUNTDOWN:  # Zustandswechsel melden
                print(f"\n{zustand}")          # neue Zeile mit dem Zustand
            vorher = zustand                   # merken
            time.sleep(0.03)                   # alle 30 ms: Bewegung wird praktisch sofort erkannt
    except KeyboardInterrupt:                  # Strg+C
        print(f"\nBeendet. Alarme gesendet: {waechter.alarme}")  # Bilanz
    finally:                                   # Cleanup laut Arbeitsblatt 6.5
        mqtt.beenden()                         # Loop stoppen, offline melden, trennen
        for geraet in (gelb, rot, sensor):     # alle Geräte
            geraet.close()                     # Pins freigeben (LEDs gehen dabei aus)


if __name__ == "__main__":                     # nur beim direkten Start
    main()                                     # los geht's
