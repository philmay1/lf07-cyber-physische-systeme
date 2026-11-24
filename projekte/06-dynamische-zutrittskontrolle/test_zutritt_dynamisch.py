"""Tests für Projekt 06: Argon2-Prüfung, fail closed und echte MariaDB (falls eingerichtet).

Teil 1 läuft überall (Datenbank wird durch eine Funktion ersetzt).
Teil 2 nutzt die echte Datenbank auf dem Pi mit einer eigenen Test-Tür "testtuer",
damit die echte Tür door01 unverändert bleibt. Ohne einrichten.sh wird Teil 2 übersprungen.
Aufruf: python3 test_zutritt_dynamisch.py
"""
import sys                                     # Suchpfad und Exit-Code
from pathlib import Path                       # Pfade

HIER = Path(__file__).resolve().parent         # Ordner dieses Tests
sys.path.insert(0, str(HIER))                  # Projektdateien importierbar
sys.path.insert(0, str(HIER.parent / "gemeinsam"))  # gemeinsame Bausteine

from argon2 import PasswordHasher              # noqa: E402  Test-Prüfwerte erzeugen

import db_adapter                              # noqa: E402  Adapter
from zutritt_ablauf import PruefFehler         # noqa: E402  technischer Fehler
from zutritt_dynamisch import pruefung_mit_datenbank  # noqa: E402  zu testende Prüfung

fehler = 0                                     # Fehlerzähler
TEST_PIN = "2580"                              # bedeutungslose Test-PIN, nur in diesem Test


def pruefe(name, ok):                          # Ergebniszeile und Zählung
    global fehler                              # globalen Zähler ändern
    print(("OK     " if ok else "FEHLER ") + name)  # Zeile
    fehler += 0 if ok else 1                   # zählen


def wirft(funktion, *args):                    # True, wenn funktion einen PruefFehler wirft
    try:                                       # ausprobieren
        funktion(*args)                        # aufrufen
        return False                           # kein Fehler: nicht wie erwartet
    except PruefFehler:                        # technischer Fehler
        return True                            # wie erwartet


# ---------- Teil 1: Logik ohne Datenbank ----------
h = PasswordHasher().hash(TEST_PIN)            # gültiger Argon2id-Prüfwert
pruefe("Prüfwert ist Argon2id und enthält keine PIN", h.startswith("$argon2id$") and TEST_PIN not in h)  # Format
v = pruefung_mit_datenbank("door01", lambda d: h)  # Datenbank durch Funktion ersetzt
pruefe("richtige PIN ergibt True", v(TEST_PIN) is True)  # granted
pruefe("falsche PIN ergibt False", v("0000") is False)  # denied
pruefe("unbekannte Tür: fail closed", wirft(pruefung_mit_datenbank("door01", lambda d: None), TEST_PIN))  # kein Datensatz
def db_weg(d):                                 # simuliert eine nicht erreichbare Datenbank
    raise db_adapter.AdapterFehler("Datenbank nicht erreichbar")  # wie der echte Adapter
pruefe("Datenbank weg: fail closed", wirft(pruefung_mit_datenbank("door01", db_weg), TEST_PIN))  # technischer Fehler
pruefe("beschädigter Prüfwert: fail closed", wirft(pruefung_mit_datenbank("door01", lambda d: "$argon2id$kaputt"), TEST_PIN))  # InvalidHash
for falsch in ("", "Door01", "door01'; DROP TABLE access_doors;--", "x" * 33):  # ungültige door_ids
    try:                                       # Format prüfen
        db_adapter.door_id_pruefen(falsch)     # muss abweisen
        pruefe(f"door_id {falsch[:20]!r} wird abgewiesen", False)  # kam durch
    except ValueError:                         # wie erwartet
        pruefe(f"door_id {falsch[:20]!r} wird abgewiesen", True)  # bestanden
try:                                           # Klartext darf nie gespeichert werden
    db_adapter.set_door_code_hash("door01", TEST_PIN)  # wäre fatal
    pruefe("Klartext-PIN wird nie gespeichert", False)  # kam durch
except ValueError:                             # wie erwartet abgewiesen, noch vor der Datenbank
    pruefe("Klartext-PIN wird nie gespeichert", True)  # bestanden

# ---------- Teil 2: echte MariaDB ----------
try:                                           # sind Zugangsdaten eingerichtet?
    db_adapter.zugang_laden("admin")           # Verwaltungskonto
    db_adapter.zugang_laden("access")          # Laufzeitkonto
    eingerichtet = True                        # ja
except db_adapter.AdapterFehler:               # nein
    eingerichtet = False                       # Teil 2 überspringen
if not eingerichtet:                           # ohne Datenbank
    print("HINWEIS Teil 2 übersprungen: erst bash einrichten.sh ausführen")  # ehrlich melden
else:                                          # mit Datenbank
    db_adapter.set_door_code_hash("testtuer", PasswordHasher().hash(TEST_PIN))  # Test-Tür anlegen (nur Hash)
    gelesen = db_adapter.get_door_code_hash("testtuer")  # über das Laufzeitkonto lesen
    pruefe("MariaDB liefert den gespeicherten Argon2-Prüfwert", gelesen is not None and gelesen.startswith("$argon2id$"))  # Roundtrip
    v = pruefung_mit_datenbank("testtuer")     # echte Prüfung über die Datenbank
    pruefe("MariaDB + Argon2: richtige PIN gewährt", v(TEST_PIN) is True)  # granted
    pruefe("MariaDB + Argon2: falsche PIN verweigert", v("1111") is False)  # denied
    pruefe("Tür ohne Datensatz: fail closed", wirft(pruefung_mit_datenbank("gibtesnicht"), TEST_PIN))  # None -> Fehler
    import mysql.connector                     # direkt prüfen, dass das Laufzeitkonto nicht schreiben darf
    conn = db_adapter.verbinden("access")      # Laufzeitkonto
    try:                                       # Schreibversuch
        conn.cursor().execute("UPDATE access_doors SET door_code_hash = %s WHERE door_id = %s", ("x", "testtuer"))  # verboten
        pruefe("Laufzeitkonto darf nicht schreiben (Minimalrecht)", False)  # ging durch
    except mysql.connector.Error:              # Zugriff verweigert
        pruefe("Laufzeitkonto darf nicht schreiben (Minimalrecht)", True)  # bestanden
    finally:                                   # immer
        conn.close()                           # Verbindung schließen

print()                                        # Leerzeile
print("Alle Tests bestanden." if fehler == 0 else f"{fehler} Test(s) fehlgeschlagen.")  # Fazit
sys.exit(1 if fehler else 0)                   # Exit-Code
