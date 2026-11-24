"""SENTINEL Projekt 06: Dynamische Zutrittskontrolle mit MariaDB und Argon2 (Tag 6, AB3).

Gleicher Aufbau wie Projekt 05 (Keypad, Servo, LEDs, Summer). Neu ist nur die Prüfung:
Die getippte PIN wird mit Argon2 gegen den Prüfwert aus MariaDB verglichen.
Fail closed: Ist die Datenbank weg, die Tür unbekannt oder der Prüfwert kaputt, bleibt die
Tür zu und es gibt eine technische Fehlermeldung, nie ein "Zutritt gewährt".

Aufruf:  python3 zutritt_dynamisch.py           (ohne MQTT)
         python3 zutritt_dynamisch.py --mqtt    (meldet granted/denied/technical_error)
Vorher einmalig: bash einrichten.sh und python3 pin_setzen.py
"""
import argparse                                # Option --mqtt
import configparser                            # sentinel.ini lesen
import sys                                     # Suchpfad und Programmende
from pathlib import Path                       # Pfade

from argon2 import PasswordHasher              # Argon2-Prüfung
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError  # mögliche Ergebnisse der Prüfung

HIER = Path(__file__).resolve().parent         # Ordner dieses Projekts
sys.path.insert(0, str(HIER.parent / "gemeinsam"))  # projekte/gemeinsam importierbar machen

import db_adapter                              # noqa: E402  Datenbankzugriff
from zutritt_ablauf import PruefFehler, ausfuehren  # noqa: E402  gemeinsame Hauptschleife

ph = PasswordHasher()                          # Standardparameter von argon2-cffi (Argon2id)


def pruefung_mit_datenbank(door_id, hash_laden=db_adapter.get_door_code_hash):  # baut verify_pin(pin) -> bool
    def verify_pin(pin):                       # wird vom Ablauf mit der getippten PIN aufgerufen
        try:                                   # Datenbankzugriff
            gespeichert = hash_laden(door_id)  # Prüfwert holen
        except (db_adapter.AdapterFehler, ValueError) as fehler:  # Datenbank weg oder door_id ungültig
            raise PruefFehler(str(fehler)) from None  # technischer Fehler: Tür bleibt zu
        if gespeichert is None:                # Tür nicht in der Datenbank
            raise PruefFehler(f"kein Prüfwert für {door_id}")  # fail closed
        try:                                   # Argon2-Vergleich
            return ph.verify(gespeichert, pin)  # True, wenn die PIN passt
        except VerifyMismatchError:            # PIN passt nicht
            return False                       # ganz normales "falsch"
        except (InvalidHash, VerificationError):  # Prüfwert in der Datenbank ist beschädigt
            raise PruefFehler("Prüfwert ist beschädigt") from None  # technischer Fehler, Tür bleibt zu
    return verify_pin                          # Funktion zurückgeben


def door_id_laden(pfad=HIER / "sentinel.ini"):  # nicht geheime Konfiguration
    cfg = configparser.ConfigParser()          # INI-Leser
    cfg.read(pfad, encoding="utf-8")           # Datei lesen
    door_id = cfg.get("access", "door_id", fallback="")  # Türkennung
    try:                                       # Format prüfen
        db_adapter.door_id_pruefen(door_id)    # wirft bei leer oder ungültig
    except ValueError:                         # HS-03: fehlende door_id
        sys.exit("door_id fehlt oder ist ungültig in sentinel.ini. Start abgelehnt, Tür bleibt zu.")  # fail closed
    return door_id                             # gültige door_id


def main():                                    # Hauptprogramm
    parser = argparse.ArgumentParser(description="SENTINEL dynamische Zutrittskontrolle")  # Optionen
    parser.add_argument("--mqtt", action="store_true", help="Zutrittsereignisse per MQTT melden")  # optional
    args = parser.parse_args()                 # lesen
    door_id = door_id_laden()                  # Konfiguration prüfen, bevor Hardware angefasst wird
    db_adapter.zugang_laden("access")          # Zugangsdaten vorhanden? Sonst sofort klarer Abbruch

    from keypad import Keypad                  # Keypad-Scanner
    from tuer import Tuer                      # Servo und Rückmeldung

    mqtt = None                                # ohne --mqtt bleibt das None
    if args.mqtt:                              # mit MQTT
        from mqtt_verbindung import Modul      # Verbindung mit Last Will
        mqtt = Modul("access", "sentinel-door01")  # Modul Zutrittskontrolle
        print("MQTT verbunden" if mqtt.starten(5.0) else "MQTT nicht erreichbar, lokal geht es weiter")  # Status
    keypad, tuer = Keypad(), Tuer()            # Hardware anlegen; Tür fährt in Startposition 0°
    try:                                       # geschützter Block
        ausfuehren(keypad, tuer, pruefung_mit_datenbank(door_id), mqtt)  # Hauptschleife mit Datenbankprüfung
    except KeyboardInterrupt:                  # Strg+C
        print("\nBeendet.")                    # Abschluss
    finally:                                   # Cleanup
        tuer.schliessen()                      # verriegeln, PWM aus, LEDs aus
        keypad.schliessen()                    # Keypad-Pins frei
        if mqtt:                               # nur wenn MQTT benutzt wurde
            mqtt.beenden()                     # offline melden und trennen


if __name__ == "__main__":                     # nur beim direkten Start
    main()                                     # los geht's
