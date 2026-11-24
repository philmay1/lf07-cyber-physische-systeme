"""SENTINEL Projekt 05: Lokale Zutrittskontrolle mit Keypad und Servo (Tag 5, AB3).

PIN am 4x4-Keypad tippen, # prüft. Richtig: grün, zwei Pieptöne, Servo 0° -> 90° -> 3 s -> 0°.
Falsch: rot 1 s, der Servo bewegt sich nicht.

Die PIN steht in diesem Lernschritt bewusst im Klartext in config.ini. Das ist laut
Arbeitsblatt eine unsichere Lernstufe: config.ini ist per .gitignore ausgeschlossen, im Repo
liegt nur config.example.ini. Projekt 06 ersetzt diese Prüfung durch MariaDB mit Argon2.

Aufruf:  python3 zutritt_lokal.py           (ohne MQTT)
         python3 zutritt_lokal.py --mqtt    (meldet granted/denied an sentinel/lab01/access/door01/event)
"""
import argparse                                # Option --mqtt
import configparser                            # config.ini lesen
import hmac                                    # Vergleich in konstanter Zeit
import sys                                     # Suchpfad und Programmende
from pathlib import Path                       # Pfade

HIER = Path(__file__).resolve().parent         # Ordner dieses Projekts
sys.path.insert(0, str(HIER.parent / "gemeinsam"))  # projekte/gemeinsam importierbar machen

from zutritt_ablauf import ausfuehren          # noqa: E402  gemeinsame Hauptschleife


def konfiguration_laden(pfad=HIER / "config.ini"):  # liest door_id, PIN und Timeout
    if not pfad.exists():                      # ohne config.ini kein Zutrittsbetrieb
        sys.exit("config.ini fehlt. Kopiere config.example.ini nach config.ini und trage eine Test-PIN ein.")  # klare Anleitung
    cfg = configparser.ConfigParser()          # INI-Datei-Leser
    cfg.read(pfad, encoding="utf-8")           # Datei einlesen
    abschnitt = cfg["access"]                  # Abschnitt [access]
    pin = abschnitt.get("pin", "")             # Test-PIN (Klartext, nur Lernstufe)
    if len(pin) != 4 or not pin.isdigit():     # muss genau 4 Ziffern haben
        sys.exit("pin in config.ini muss genau 4 Ziffern haben")  # fail closed: lieber gar nicht starten
    timeout = abschnitt.getfloat("input_timeout_seconds", 10.0)  # Timeout, Standard 10 s
    return pin, timeout                        # beide Werte zurückgeben


def lokale_pruefung(soll):                     # baut die Prüffunktion verify_pin(pin) -> bool
    def verify_pin(pin):                       # wird vom Ablauf mit der getippten PIN aufgerufen
        return hmac.compare_digest(pin.encode(), soll.encode())  # vergleicht immer gleich lang, verrät nichts über die Zeit
    return verify_pin                          # Funktion zurückgeben


def main():                                    # Hauptprogramm
    parser = argparse.ArgumentParser(description="SENTINEL lokale Zutrittskontrolle")  # Optionen
    parser.add_argument("--mqtt", action="store_true", help="Zutrittsereignisse per MQTT melden")  # optional laut AB3
    args = parser.parse_args()                 # lesen
    soll, timeout = konfiguration_laden()      # config.ini prüfen, bevor Hardware angefasst wird

    from keypad import Keypad                  # Keypad-Scanner (erst hier, damit der Test ohne GPIO importieren kann)
    from tuer import Tuer                      # Servo und Rückmeldung

    mqtt = None                                # ohne --mqtt bleibt das None
    if args.mqtt:                              # mit MQTT
        from mqtt_verbindung import Modul      # Verbindung mit Last Will
        mqtt = Modul("access", "sentinel-door01")  # Modul Zutrittskontrolle
        print("MQTT verbunden" if mqtt.starten(5.0) else "MQTT nicht erreichbar, lokal geht es weiter")  # Status
    keypad, tuer = Keypad(), Tuer()            # Hardware anlegen; Tür fährt in Startposition 0°
    try:                                       # geschützter Block
        ausfuehren(keypad, tuer, lokale_pruefung(soll), mqtt, timeout)  # Hauptschleife
    except KeyboardInterrupt:                  # Strg+C
        print("\nBeendet.")                    # Abschluss
    finally:                                   # Cleanup in fester Reihenfolge (ZT-09)
        tuer.schliessen()                      # verriegeln, PWM aus, LEDs aus
        keypad.schliessen()                    # Keypad-Pins frei
        if mqtt:                               # nur wenn MQTT benutzt wurde
            mqtt.beenden()                     # offline melden und trennen


if __name__ == "__main__":                     # nur beim direkten Start
    main()                                     # los geht's
