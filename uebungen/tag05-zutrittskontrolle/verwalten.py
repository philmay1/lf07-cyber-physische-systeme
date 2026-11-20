#!/usr/bin/env python3
"""Benutzer und Sperre der Zutrittskontrolle verwalten.

    python3 verwalten.py neu <name> [--admin]   Benutzer anlegen, PIN wird verdeckt abgefragt
    python3 verwalten.py liste                  alle Benutzer
    python3 verwalten.py protokoll              die letzten Versuche
    python3 verwalten.py status                 Sperre und Fehlerzähler
    python3 verwalten.py entsperren             Sperre sofort aufheben
"""
# Der Docstring oben wird nicht ausgeführt. Er dient als Hilfetext (python3 verwalten.py -h).

# argparse liest die Befehle beim Start, z. B. "neu Phil".
import argparse

# getpass fragt die PIN ab, ohne sie auf dem Bildschirm anzuzeigen.
import getpass

# time wandelt die gespeicherte Unix-Zeit in lesbares Datum und Uhrzeit um.
import time

# Unsere Datenbank-Datei zutritt_db.py, hier kurz "db".
import zutritt_db as db


# Das Hauptprogramm.
def main():
    # Befehlszeile einrichten. Der Docstring wird als Beschreibung angezeigt.
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # Unterbefehle (neu, liste, ...). required=True: Ohne Befehl gibt es eine Fehlermeldung.
    sub = p.add_subparsers(dest="befehl", required=True)
    # Befehl "neu" anlegen.
    neu = sub.add_parser("neu")
    # "neu" braucht einen Namen.
    neu.add_argument("name")
    # Optional: --admin macht den Benutzer zum Admin.
    neu.add_argument("--admin", action="store_true", help="darf im Dashboard entsperren")
    # Die übrigen Befehle brauchen keine weiteren Angaben.
    for b in ("liste", "protokoll", "status", "entsperren"):
        sub.add_parser(b)
    # Befehlszeile auswerten.
    a = p.parse_args()
    # Datenbank öffnen.
    con = db.verbinden()

    # Befehl "neu": Benutzer anlegen.
    if a.befehl == "neu":
        # PIN verdeckt abfragen.
        pin = getpass.getpass("PIN (4 bis 8 Ziffern): ")
        # Zur Sicherheit ein zweites Mal abfragen und vergleichen.
        if pin != getpass.getpass("PIN wiederholen: "):
            print("PINs stimmen nicht überein.")
            return
        # Benutzer speichern. Rolle admin oder nutzer, je nach --admin.
        db.benutzer_anlegen(con, a.name, pin, "admin" if a.admin else "nutzer")
        print(f"Benutzer {a.name} angelegt.")
    # Befehl "liste": alle Benutzer anzeigen.
    elif a.befehl == "liste":
        # Jede Zeile aus der Tabelle benutzer lesen (ohne Hash, der gehört nicht auf den Bildschirm).
        for b in con.execute("SELECT id, name, rolle, aktiv FROM benutzer"):
            # Als Tabelle ausgeben. :>3 rechtsbündig 3 Zeichen, :<15 linksbündig 15 Zeichen.
            print(f"{b['id']:>3}  {b['name']:<15} {b['rolle']:<7} {'aktiv' if b['aktiv'] else 'inaktiv'}")
    # Befehl "protokoll": die letzten 30 Versuche.
    elif a.befehl == "protokoll":
        for v in db.letzte_versuche(con, 30):
            # Unix-Zeit in "Tag.Monat. Stunde:Minute:Sekunde" umwandeln.
            zeit = time.strftime("%d.%m. %H:%M:%S", time.localtime(v["zeit"]))
            # Eine Zeile pro Versuch: Zeit, OK/FEHLER, Name (oder -), Hinweis.
            print(f"{zeit}  {'OK    ' if v['erfolg'] else 'FEHLER'}  {v['name'] or '-':<12} {v['hinweis'] or ''}")
    # Befehl "status": Sperr-Zustand anzeigen.
    elif a.befehl == "status":
        s = db.status(con)
        print(f"gesperrt: {'ja, noch %.0f s' % s['rest'] if s['gesperrt'] else 'nein'}, "
              f"Fehlversuche: {s['fehlversuche']}, Sperrstufe: {s['sperr_stufe']}")
    # Befehl "entsperren": Sperre sofort aufheben.
    elif a.befehl == "entsperren":
        # Im Protokoll steht dann "entsperrt durch verwalten.py".
        db.entsperren(con, "verwalten.py")
        print("Entsperrt.")


# Nur beim direkten Start ausführen.
if __name__ == "__main__":
    main()
