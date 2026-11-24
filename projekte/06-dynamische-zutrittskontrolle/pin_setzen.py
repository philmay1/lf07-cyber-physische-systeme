"""Tür-PIN setzen: PIN verdeckt eingeben, mit Argon2id hashen, nur den Hash speichern (Tag 6, AB2).

Aufruf auf dem Pi:  python3 pin_setzen.py            (Tür aus sentinel.ini, z. B. door01)
Die PIN erscheint nie auf dem Bildschirm, in Logs oder im Repo.
"""
import configparser                            # door_id aus sentinel.ini lesen
import getpass                                 # Eingabe ohne Anzeige am Bildschirm
import sys                                     # Programmende mit Meldung
from pathlib import Path                       # Pfade

from argon2 import PasswordHasher              # Argon2id-Hashing mit Salt

import db_adapter                              # Datenbankzugriff mit Verwaltungskonto

HIER = Path(__file__).resolve().parent         # Ordner dieses Projekts


def main():                                    # Hauptprogramm
    cfg = configparser.ConfigParser()          # INI-Leser
    cfg.read(HIER / "sentinel.ini", encoding="utf-8")  # nicht geheime Konfiguration
    door_id = cfg.get("access", "door_id", fallback="")  # welche Tür
    db_adapter.door_id_pruefen(door_id)        # Format prüfen, bevor etwas passiert
    pin = getpass.getpass(f"Neue 4-stellige PIN für {door_id}: ")  # verdeckte Eingabe
    if len(pin) != 4 or not pin.isdigit():     # genau 4 Ziffern, wie am Keypad
        sys.exit("Die PIN muss genau 4 Ziffern haben.")  # abbrechen, nichts gespeichert
    if getpass.getpass("PIN wiederholen: ") != pin:  # Tippfehler abfangen
        sys.exit("Die beiden Eingaben stimmen nicht überein.")  # abbrechen
    hash_wert = PasswordHasher().hash(pin)     # Argon2id mit zufälligem Salt; der Salt steckt im String
    del pin                                    # Klartext sofort vergessen
    db_adapter.set_door_code_hash(door_id, hash_wert)  # nur den Hash speichern
    print(f"Prüfwert für {door_id} gespeichert.")  # Rückmeldung ohne PIN und ohne Hash


if __name__ == "__main__":                     # nur beim direkten Start
    main()                                     # los geht's
