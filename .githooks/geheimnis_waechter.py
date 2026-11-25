#!/usr/bin/env python3
"""Commit-Wächter: bricht einen Commit ab, wenn Geheimnisse darin stecken (Tag 8).

Git startet dieses Skript vor jedem Commit über .githooks/pre-commit.
Einschalten (einmal pro Klon):   git config core.hooksPath .githooks

Zwei Prüfungen:
1. Dateinamen: .env, .env.password, access.env usw. dürfen nicht ins Repo, auch nicht mit "git add -f".
   Erlaubt sind nur Vorlagen wie .env.example.
2. Inhalte: Jeder Passwort-Wert aus den echten Geheimnis-Dateien auf diesem Rechner wird in allen
   vorgemerkten Dateien gesucht. Das fängt auch den Fall, dass jemand ein Passwort in den Code kopiert.

Das Skript zeigt nie ein Passwort an, nur Datei und Name der Variable.
"""
# Die erste Zeile (#!) sagt Linux, dass Python 3 diese Datei ausführen soll.
# Der Docstring darunter wird nicht ausgeführt. Er erklärt Zweck und Einschalten.

# os durchsucht Ordner nach Geheimnis-Dateien.
import os

# subprocess fragt Git, welche Dateien für den Commit vorgemerkt sind.
import subprocess

# sys beendet das Skript mit Code 0 (Commit erlaubt) oder 1 (Commit abgebrochen).
import sys

# Path baut Pfade.
from pathlib import Path

# Vorlagen dürfen ins Repo. Sie enthalten nur Platzhalter.
VORLAGEN = {".env.example", ".env.sample", ".env.template"}
# Variablen mit diesen Wortteilen gelten als Geheimnis (Groß/klein egal).
GEHEIM_WOERTER = ("PASS", "SECRET", "TOKEN", "KEY")
# Kürzere Werte prüfen wir nicht, sonst schlägt der Wächter bei "1883" oder "true" Alarm.
MINDESTLAENGE = 8
# Zusätzliche Orte mit Geheimnissen außerhalb des Repos (Projekt 06 legt dort access.env ab).
EXTRA_ORDNER = [Path("/etc/sentinel")]


# Ist das ein Dateiname, der nach Geheimnis aussieht?
def geheimer_name(pfad):
    name = Path(pfad).name
    # Vorlagen sind erlaubt.
    if name in VORLAGEN:
        return False
    # .env, .env.password, .env.local ... und alles, was auf .env endet (z. B. access.env).
    return name == ".env" or name.startswith(".env.") or name.endswith(".env")


# Liest NAME=wert-Zeilen und gibt nur die geheimen Werte zurück: {wert: (datei, name)}.
def geheimnisse_aus(datei, alle_werte):
    funde = {}
    try:
        text = datei.read_text(encoding="utf-8")
    # Keine Leserechte (z. B. root-Datei)? Dann überspringen.
    except (OSError, UnicodeDecodeError):
        return funde
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        name, wert = zeile.split("=", 1)
        name, wert = name.strip(), wert.strip().strip('"').strip("'")
        # In .env.password ist jeder Wert geheim, sonst nur Variablen mit "PASS", "TOKEN" usw. im Namen.
        if len(wert) >= MINDESTLAENGE and (alle_werte or any(w in name.upper() for w in GEHEIM_WOERTER)):
            funde[wert] = (datei, name)
    return funde


# Sammelt alle Geheimnisse, die auf diesem Rechner in Geheimnis-Dateien liegen.
def geheimnisse_sammeln(wurzel):
    funde = {}
    orte = [wurzel] + [o for o in EXTRA_ORDNER if o.is_dir()]
    for ort in orte:
        for ordner, unterordner, dateien in os.walk(ort):
            # Den .git-Ordner und virtuelle Umgebungen nicht durchsuchen.
            unterordner[:] = [u for u in unterordner if u not in (".git", ".venv", "venv", "__pycache__")]
            for d in dateien:
                if geheimer_name(d):
                    funde.update(geheimnisse_aus(Path(ordner) / d, alle_werte=d.endswith(".password")))
    return funde


# Hauptteil: vorgemerkte Dateien prüfen.
def main():
    # Oberster Ordner des Repos. Git liefert UTF-8; ausdrücklich so lesen, sonst wird unter
    # Windows aus "ergänzen" Zeichensalat und der Pfad stimmt nicht mehr.
    wurzel = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"],
                                 capture_output=True, check=True).stdout.decode("utf-8").strip())
    # Alle Dateien, die im Commit landen würden (hinzugefügt, kopiert, geändert).
    vorgemerkt = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM", "-z"],
                                capture_output=True, check=True, cwd=wurzel).stdout.decode("utf-8").split("\0")
    vorgemerkt = [v for v in vorgemerkt if v]
    probleme = []
    # Prüfung 1: verbotene Dateinamen.
    for v in vorgemerkt:
        if geheimer_name(v):
            probleme.append(f"{v}: Geheimnis-Datei darf nicht ins Repo (nur .env.example als Vorlage)")
    # Prüfung 2: Passwort-Werte im Inhalt suchen. Gelesen wird der vorgemerkte Stand (git show :pfad).
    geheim = geheimnisse_sammeln(wurzel)
    for v in vorgemerkt:
        inhalt = subprocess.run(["git", "show", f":{v}"], capture_output=True, cwd=wurzel).stdout
        for wert, (quelle, name) in geheim.items():
            if wert.encode("utf-8") in inhalt:
                probleme.append(f"{v}: enthält den Wert von {name} aus {quelle.name}")
    # Alles sauber? Commit erlauben.
    if not probleme:
        return 0
    # Sonst abbrechen und erklären, was zu tun ist.
    print("\n  COMMIT GESTOPPT vom Geheimnis-Wächter (.githooks/geheimnis_waechter.py)\n", file=sys.stderr)
    for p in probleme:
        print("   - " + p, file=sys.stderr)
    print("\n  So geht es weiter:\n"
          "   git restore --staged <datei>   Datei aus dem Commit nehmen\n"
          "   Passwort aus dem Code entfernen und über .env.password / Umgebungsvariable lesen\n"
          "   War das Passwort schon einmal auf GitHub? Dann sofort ändern.\n", file=sys.stderr)
    return 1


# Nur beim direkten Start ausführen.
if __name__ == "__main__":
    sys.exit(main())
