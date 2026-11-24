"""Gemeinsamer Ablauf der Zutrittskontrolle für Projekt 05 und 06.

Keypad lesen -> PIN-Eingabe -> verify_pin(pin) -> Tür öffnen oder ablehnen -> optional MQTT.
Die Prüffunktion wird von außen übergeben: Projekt 05 prüft lokal gegen config.ini,
Projekt 06 gegen MariaDB mit Argon2. Scanner, Servo und Rückmeldung bleiben gleich (AB3, Codegrenze Tag 6).
"""
import time                                    # monotone Zeit und Scan-Takt

import vertrag                                 # Payload für das Zutrittsereignis
from pin_eingabe import PinEingabe             # Zustandsautomat für die PIN

SCAN_S = 0.02                                  # alle 20 ms scannen


class PruefFehler(Exception):                  # technischer Fehler bei der Prüfung, z. B. Datenbank nicht erreichbar
    """Die PIN konnte nicht geprüft werden. Die Tür bleibt zu (fail closed)."""


def ereignis_senden(mqtt, ergebnis):           # meldet granted, denied oder technical_error, nie die PIN
    if mqtt is None:                           # MQTT ist optional
        return                                 # dann nichts senden
    status = {"granted": "normal", "denied": "warning"}.get(ergebnis, "alarm")  # Status laut erlaubter Werteliste
    daten = vertrag.nachricht("access", "access_attempt", status, access_result=ergebnis)  # Vertrag 3.6
    mqtt.senden("event", daten)                # QoS 1, nicht retained


def ausfuehren(keypad, tuer, verify_pin, mqtt=None, timeout_s=10.0, laufen=lambda: True):  # Hauptschleife
    eingabe = PinEingabe(timeout_s)            # leere Eingabe, Tür ist verriegelt
    print("Zutrittskontrolle bereit: 4 Ziffern, # prüft, * löscht. Strg+C beendet.")  # Startmeldung
    while laufen():                            # im Betrieb endlos, im Test begrenzt
        jetzt = time.monotonic()               # aktuelle Zeit
        if eingabe.timeout_pruefen(jetzt):     # angefangene Eingabe verfallen?
            print("Timeout: Eingabe gelöscht")  # Hinweis, ohne Ziffern
            tuer.hinweis()                     # zweimal rot blinken
        zeichen = keypad.taste()               # neue Taste oder None
        if zeichen is None:                    # nichts gedrückt
            time.sleep(SCAN_S)                 # kurz warten
            continue                           # nächster Scan
        tuer.taste_quittieren()                # gelb blitzt bei jeder Taste
        ergebnis = eingabe.taste(zeichen, jetzt)  # Zustandsautomat entscheiden lassen
        if ergebnis == "unvollstaendig":       # # bei weniger als 4 Ziffern
            print("Bitte genau 4 Ziffern eingeben")  # Hinweis
            tuer.hinweis()                     # zweimal rot blinken
        elif isinstance(ergebnis, tuple):      # ("pruefen", pin)
            pin = ergebnis[1]                  # PIN nur kurz in dieser Variablen
            try:                               # Prüfung kann technisch scheitern
                ok = verify_pin(pin)           # True oder False
            except PruefFehler as fehler:      # technischer Fehler
                ok = None                      # weder richtig noch falsch
                print(f"Technischer Fehler, Tür bleibt zu: {fehler}")  # ohne PIN
            finally:                           # in jedem Fall
                del pin                        # PIN sofort vergessen
            if ok is True:                     # richtig
                print("Zutritt gewährt")       # Ergebnis ohne PIN (ZT-12)
                ereignis_senden(mqtt, "granted")  # optional melden
                tuer.oeffnen()                 # 0° -> 90° -> 3 s -> 0°
                keypad.taste()                 # Tasten, die während der Sequenz gedrückt wurden, verwerfen
            elif ok is False:                  # falsch
                print("Zutritt verweigert")    # Ergebnis ohne PIN
                ereignis_senden(mqtt, "denied")  # optional melden
                tuer.falsch()                  # rot 1 s, keine Bewegung
            else:                              # technischer Fehler
                ereignis_senden(mqtt, "technical_error")  # melden, ohne interne Details
                tuer.fehler()                  # rot langsam blinkend
