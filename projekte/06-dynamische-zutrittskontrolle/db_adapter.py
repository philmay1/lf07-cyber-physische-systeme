"""Datenbank-Adapter für access_doors (Tag 6, AB1 Adaptergerüst).

Kapselt den Zugriff auf MariaDB: liefert für eine door_id genau einen Argon2-Prüfwert
oder None. Technische Probleme werden als AdapterFehler gemeldet. Es wird nie eine PIN,
nie ein Hash und nie ein Passwort ausgegeben. SQL nur mit Parameterbindung (kein SQL-Injection-Risiko).
"""
import os                                      # Zugangsdaten aus Umgebungsvariablen
import re                                      # door_id-Format prüfen
from pathlib import Path                       # Pfad der env-Datei
from typing import Optional                    # Typangabe "str oder None" (Python 3.9 kennt str | None noch nicht)

DOOR_ID_MUSTER = re.compile(r"^[a-z0-9-]{1,32}$")  # technisches Format: klein, Ziffern, Bindestrich, max. 32 Zeichen


class AdapterFehler(Exception):                # Datenbank nicht erreichbar, Zugang falsch, Daten kaputt
    """Technischer Fehler beim Datenbankzugriff."""


class DatenIntegritaetsFehler(AdapterFehler):  # mehr als ein Datensatz für eine door_id
    """Die Datenbank liefert unerwartete Daten."""


def zugang_laden(rolle="access"):              # liest /etc/sentinel/<rolle>.env, falls die Werte nicht schon gesetzt sind
    datei = Path(os.environ.get("SENTINEL_ENV_DIR", "/etc/sentinel")) / f"{rolle}.env"  # Standardort laut AB2
    werte = {}                                 # hier landen die Einträge
    if datei.exists():                         # Datei vorhanden
        for zeile in datei.read_text(encoding="utf-8").splitlines():  # Zeile für Zeile
            if "=" in zeile and not zeile.startswith("#"):  # nur KEY=WERT, keine Kommentare
                k, v = zeile.split("=", 1)     # an der ersten = trennen
                werte[k.strip()] = v.strip()   # merken
    for k in ("SENTINEL_DB_HOST", "SENTINEL_DB_NAME", "SENTINEL_DB_USER", "SENTINEL_DB_PASSWORD"):  # benötigte Werte
        werte[k] = os.environ.get(k, werte.get(k))  # Umgebungsvariable hat Vorrang (z. B. systemd EnvironmentFile)
    if not all(werte.get(k) for k in ("SENTINEL_DB_HOST", "SENTINEL_DB_NAME", "SENTINEL_DB_USER", "SENTINEL_DB_PASSWORD")):  # etwas fehlt
        raise AdapterFehler(f"Zugangsdaten fehlen ({datei} oder Umgebungsvariablen)")  # ohne Passwort zu nennen
    return werte                               # vollständige Zugangsdaten


def door_id_pruefen(door_id):                  # Eingabe validieren, bevor die Datenbank gefragt wird
    if not isinstance(door_id, str) or not DOOR_ID_MUSTER.match(door_id):  # falscher Typ oder falsches Format
        raise ValueError("door_id hat ein ungültiges Format")  # fail closed: keine Abfrage


def verbinden(rolle="access"):                 # öffnet eine Datenbankverbindung mit kurzem Timeout
    import mysql.connector                     # erst hier importieren, damit Tests ohne Connector laufen
    z = zugang_laden(rolle)                    # Zugangsdaten holen
    try:                                       # Verbindungsaufbau kann scheitern
        return mysql.connector.connect(        # Verbindung öffnen
            host=z["SENTINEL_DB_HOST"], database=z["SENTINEL_DB_NAME"],  # wohin
            user=z["SENTINEL_DB_USER"], password=z["SENTINEL_DB_PASSWORD"],  # mit welchem Konto
            connection_timeout=3,              # höchstens 3 s warten, die Tür bleibt währenddessen zu
        )
    except mysql.connector.Error as fehler:    # Dienst aus, Passwort falsch, Rechte fehlen ...
        raise AdapterFehler(f"Datenbank nicht erreichbar (Fehler {fehler.errno})") from None  # nur die Fehlernummer, keine Details


def get_door_code_hash(door_id) -> Optional[str]:  # liefert genau einen Prüfwert oder None
    door_id_pruefen(door_id)                   # erst Eingabe prüfen
    import mysql.connector                     # für die Fehlerklasse
    conn = cursor = None                       # für finally vorbelegen
    try:                                       # alles, was schiefgehen kann
        conn = verbinden("access")             # Laufzeitkonto (nur SELECT)
        cursor = conn.cursor()                 # Abfrageobjekt
        cursor.execute("SELECT door_code_hash FROM access_doors WHERE door_id = %s", (door_id,))  # Parameterbindung, nie Text zusammensetzen
        zeilen = cursor.fetchall()             # alle Ergebniszeilen
        if len(zeilen) == 0:                   # Tür unbekannt
            return None                        # kein Prüfwert
        if len(zeilen) != 1:                   # darf wegen PRIMARY KEY nie passieren
            raise DatenIntegritaetsFehler("mehr als ein Datensatz für door_id")  # trotzdem abfangen
        return zeilen[0][0]                    # der Argon2-String
    except mysql.connector.Error as fehler:    # Fehler während der Abfrage
        raise AdapterFehler(f"Abfrage fehlgeschlagen (Fehler {fehler.errno})") from None  # ohne SQL-Parameter
    finally:                                   # Ressourcen immer schließen
        if cursor:                             # nur wenn angelegt
            cursor.close()                     # Abfrageobjekt schließen
        if conn:                               # nur wenn verbunden
            conn.close()                       # Verbindung schließen


def set_door_code_hash(door_id, hash_wert):    # nur für pin_setzen.py: Prüfwert anlegen oder ersetzen
    door_id_pruefen(door_id)                   # Eingabe prüfen
    if not hash_wert.startswith("$argon2id$"):  # nur vollständige Argon2id-Prüfwerte zulassen
        raise ValueError("kein Argon2id-Prüfwert")  # schützt vor versehentlich gespeicherter Klartext-PIN
    conn = verbinden("admin")                  # Verwaltungskonto (INSERT, UPDATE)
    try:                                       # Verbindung in jedem Fall schließen
        cursor = conn.cursor()                 # Abfrageobjekt
        cursor.execute(                        # anlegen oder, falls vorhanden, ersetzen
            "INSERT INTO access_doors (door_id, door_code_hash) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE door_code_hash = VALUES(door_code_hash)",  # MariaDB-Syntax für "einfügen oder ändern"
            (door_id, hash_wert),              # Parameterbindung
        )
        conn.commit()                          # Änderung dauerhaft speichern
        cursor.close()                         # Abfrageobjekt schließen
    finally:                                   # immer
        conn.close()                           # Verbindung schließen
