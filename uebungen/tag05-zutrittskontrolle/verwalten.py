#!/usr/bin/env python3
"""Benutzer und Sperre der Zutrittskontrolle verwalten.

    python3 verwalten.py neu <name> [--admin]   Benutzer anlegen, PIN wird verdeckt abgefragt
    python3 verwalten.py liste                  alle Benutzer
    python3 verwalten.py protokoll              die letzten Versuche
    python3 verwalten.py status                 Sperre und Fehlerzähler
    python3 verwalten.py entsperren             Sperre sofort aufheben
"""
import argparse
import getpass
import time

import zutritt_db as db


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="befehl", required=True)
    neu = sub.add_parser("neu")
    neu.add_argument("name")
    neu.add_argument("--admin", action="store_true", help="darf im Dashboard entsperren")
    for b in ("liste", "protokoll", "status", "entsperren"):
        sub.add_parser(b)
    a = p.parse_args()
    con = db.verbinden()

    if a.befehl == "neu":
        pin = getpass.getpass("PIN (4 bis 8 Ziffern): ")
        if pin != getpass.getpass("PIN wiederholen: "):
            print("PINs stimmen nicht überein.")
            return
        db.benutzer_anlegen(con, a.name, pin, "admin" if a.admin else "nutzer")
        print(f"Benutzer {a.name} angelegt.")
    elif a.befehl == "liste":
        for b in con.execute("SELECT id, name, rolle, aktiv FROM benutzer"):
            print(f"{b['id']:>3}  {b['name']:<15} {b['rolle']:<7} {'aktiv' if b['aktiv'] else 'inaktiv'}")
    elif a.befehl == "protokoll":
        for v in db.letzte_versuche(con, 30):
            zeit = time.strftime("%d.%m. %H:%M:%S", time.localtime(v["zeit"]))
            print(f"{zeit}  {'OK    ' if v['erfolg'] else 'FEHLER'}  {v['name'] or '-':<12} {v['hinweis'] or ''}")
    elif a.befehl == "status":
        s = db.status(con)
        print(f"gesperrt: {'ja, noch %.0f s' % s['rest'] if s['gesperrt'] else 'nein'}, "
              f"Fehlversuche: {s['fehlversuche']}, Sperrstufe: {s['sperr_stufe']}")
    elif a.befehl == "entsperren":
        db.entsperren(con, "verwalten.py")
        print("Entsperrt.")


if __name__ == "__main__":
    main()
