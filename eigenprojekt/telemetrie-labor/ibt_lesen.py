"""Liest iRacing-Telemetriedateien (.ibt) und zerlegt sie in Runden.

Aufbau einer .ibt-Datei (Binärformat, Little Endian):

    Byte 0     Kopf (112 Byte): Version, Abtastrate (60 Hz), wo die Session-Infos und die
               Variablenliste stehen, wie groß ein Datensatz ist und wo die Daten beginnen
    Byte 112   Datei-Kopf (32 Byte): Startzeit, Anzahl Runden, Anzahl Datensätze
    Byte 144   Variablenliste: pro Kanal 144 Byte mit Typ, Position im Datensatz und Name
    danach     Session-Infos als YAML-Text (Strecke, Auto, alle Fahrer der Session)
    danach     die Messwerte: ein Datensatz pro 1/60 Sekunde, alle gleich groß

Python liest nur die Kanäle, die wir brauchen. numpy legt dafür eine "Maske" über die
Datei (memmap). So wird auch eine 500-MB-Datei auf dem Pi in Sekunden gelesen, ohne
sie komplett in den Arbeitsspeicher zu laden.

Datenschutz: Die Session-Infos enthalten Namen und Kunden-IDs aller Fahrer der Session.
Wir lesen daraus nur Strecke, Streckenlänge, Art der Session und das eigene Auto.
"""
# Der Docstring oben wird nicht ausgeführt. Er erklärt das Dateiformat.

# re sucht einzelne Werte im YAML-Text (ohne Zusatzpaket).
import re

# struct liest Zahlen aus Bytes (z. B. "<10i" = zehn 4-Byte-Ganzzahlen, Little Endian).
import struct

# datetime macht aus dem Zeitstempel im Kopf ein Datum.
from datetime import datetime

# os.path.getsize liefert die Dateigröße (Fallback, falls die Datensatz-Anzahl fehlt).
import os

# numpy rechnet mit ganzen Spalten auf einmal. Pi: sudo apt install python3-numpy
import numpy as np

# Typen der Variablen laut iRacing SDK: Nummer -> numpy-Datentyp.
# 0 char, 1 bool, 2 int, 3 bitfield, 4 float, 5 double
TYPEN = {0: "u1", 1: "u1", 2: "<i4", 3: "<u4", 4: "<f4", 5: "<f8"}

# Kanäle, die wir für die Auswertung brauchen.
KANAELE = ["SessionTime", "Lap", "LapDistPct", "Speed", "Throttle", "Brake", "Gear", "RPM",
           "SteeringWheelAngle", "Lat", "Lon", "FuelLevel", "OnPitRoad", "IsOnTrack", "PlayerTrackSurface"]

# So viele Punkte bekommt jede Runde nach dem Umrechnen auf die Strecke (alle 0,1 % der Runde).
PUNKTE = 1000

# PlayerTrackSurface = 0 bedeutet: neben der Strecke (irsdk_TrkLoc OffTrack).
NEBEN_DER_STRECKE = 0


# Liest Kopf, Variablenliste und Session-Infos. Gibt ein Wörterbuch zurück.
def kopf_lesen(pfad):
    with open(pfad, "rb") as f:
        # Die ersten 144 Byte: Haupt-Kopf (112) und Datei-Kopf (32).
        k = f.read(144)
        if len(k) < 144:
            raise ValueError("Datei zu kurz, keine .ibt")
        # Zehn Ganzzahlen am Anfang.
        ver, status, takt, _, info_len, info_off, anz_var, var_off, anz_buf, satz_len = struct.unpack_from("<10i", k, 0)
        # Wo die Messwerte beginnen (erster Puffer, Byte 52).
        daten_off = struct.unpack_from("<i", k, 52)[0]
        # Datei-Kopf: Startdatum (Unix-Zeit), Start- und Endzeit der Session, Runden, Datensätze.
        start, t0, t1, runden, saetze = struct.unpack_from("<qddii", k, 112)
        # Plausibilität: Version 2 und 60 Hz sind bei iRacing üblich.
        if ver != 2 or takt <= 0 or satz_len <= 0:
            raise ValueError("unbekanntes Format (keine iRacing-.ibt?)")
        # Variablenliste lesen: pro Variable 144 Byte.
        f.seek(var_off)
        vl = f.read(144 * anz_var)
        variablen = {}
        for i in range(anz_var):
            typ, off, anzahl = struct.unpack_from("<3i", vl, i * 144)
            name = vl[i * 144 + 16:i * 144 + 48].split(b"\0")[0].decode("ascii", "replace")
            variablen[name] = (typ, off, anzahl)
        # Session-Infos (YAML) lesen. iRacing schreibt Windows-1252.
        f.seek(info_off)
        info = f.read(info_len).decode("cp1252", "replace")
    # Falls die Datei nicht sauber abgeschlossen wurde, Anzahl aus der Dateigröße berechnen.
    moeglich = (os.path.getsize(pfad) - daten_off) // satz_len
    saetze = moeglich if saetze <= 0 else min(saetze, moeglich)
    return {"takt": takt, "satz_len": satz_len, "daten_off": daten_off, "saetze": saetze,
            "variablen": variablen, "info": info, "start": start}


# Holt einen einzelnen Wert aus dem YAML-Text, z. B. "TrackDisplayName: Monza".
def yaml_wert(text, schluessel):
    m = re.search(rf"^\s*{schluessel}: (.*)$", text, re.M)
    return m.group(1).strip() if m else ""


# Liest nur die Angaben, die wir speichern wollen. Keine Fahrernamen, keine Kunden-IDs.
def session_lesen(info):
    # Streckenlänge steht als "5.7508 km" im Text.
    laenge = yaml_wert(info, "TrackLength").split(" ")[0]
    # Das eigene Auto: DriverCarIdx sagt, welcher Eintrag in der Fahrerliste wir sind.
    idx = yaml_wert(info, "DriverCarIdx")
    auto = ""
    if idx:
        # Den Block "- CarIdx: <idx>" suchen und darin CarScreenName lesen.
        m = re.search(rf"- CarIdx: {idx}\n(.*?)(?=\n\s*- CarIdx:|\Z)", info, re.S)
        if m:
            auto = yaml_wert(m.group(1), "CarScreenName")
    return {
        "strecke": yaml_wert(info, "TrackDisplayName"),
        "layout": yaml_wert(info, "TrackConfigName"),
        "laenge_m": round(float(laenge) * 1000) if laenge else 0,
        "typ": yaml_wert(info, "EventType"),
        "auto": auto,
    }


# Liest die gewünschten Kanäle als numpy-Spalten (nur lesen, nichts wird kopiert, bis man rechnet).
def kanaele_lesen(pfad, kopf):
    namen, formate, offsets = [], [], []
    for name in KANAELE:
        if name not in kopf["variablen"]:
            raise ValueError(f"Kanal {name} fehlt in der Datei")
        typ, off, _ = kopf["variablen"][name]
        namen.append(name)
        formate.append(TYPEN[typ])
        offsets.append(off)
    # Ein "Datensatz-Typ": welche Spalte an welchem Byte steht und wie groß ein Satz ist.
    satz = np.dtype({"names": namen, "formats": formate, "offsets": offsets, "itemsize": kopf["satz_len"]})
    # memmap: die Datei wird wie ein Array behandelt, gelesen wird nur, was man anfasst.
    return np.memmap(pfad, dtype=satz, mode="r", offset=kopf["daten_off"], shape=(kopf["saetze"],))


# Findet die Zeitpunkte, an denen das Auto die Ziellinie überquert.
def ziellinien(d):
    pct = d["LapDistPct"].astype("f8")
    t = d["SessionTime"].astype("f8")
    # Übergang von fast 100 % auf fast 0 % = Ziellinie. Lap muss dabei um 1 steigen.
    i = np.where((pct[:-1] > 0.9) & (pct[1:] < 0.1) & (np.diff(d["Lap"]) == 1))[0] + 1
    # Genauer Zeitpunkt zwischen zwei Messungen (lineare Interpolation).
    vorher, nachher = 1.0 - pct[i - 1], pct[i]
    anteil = vorher / np.maximum(vorher + nachher, 1e-9)
    zeiten = t[i - 1] + anteil * (t[i] - t[i - 1])
    return i, zeiten


# Zerlegt die Datei in Runden und rechnet jede Runde auf 1000 Punkte entlang der Strecke um.
def runden_bauen(d, takt):
    idx, zeiten = ziellinien(d)
    t = d["SessionTime"].astype("f8")
    runden = []
    for k in range(len(idx) - 1):
        a, b = idx[k], idx[k + 1]
        # Datensätze dieser Runde (inklusive des ersten der nächsten, für sauberes Ende).
        s = slice(a - 1, b + 1)
        tt = t[s]
        # Streckenanteil "auspacken": vor der Linie negativ, nach der Linie über 1.
        pct = d["LapDistPct"][s].astype("f8")
        pct[0] -= 1.0
        pct[-1] += 1.0
        zeit = float(zeiten[k + 1] - zeiten[k])
        # Gültigkeit prüfen: ganz auf der Strecke, nie in der Box, keine Lücken in der Aufzeichnung.
        grund = ""
        if np.any(d["OnPitRoad"][a:b]):
            grund = "Box"
        elif not np.all(d["IsOnTrack"][a:b]):
            grund = "nicht auf der Strecke"
        elif np.count_nonzero(d["PlayerTrackSurface"][a:b] == NEBEN_DER_STRECKE) > takt // 2:
            grund = "Ausritt"
        elif np.max(np.diff(tt)) > 1.0:
            grund = "Lücke in der Aufzeichnung"
        # Auf ein festes Raster umrechnen: 1000 Punkte von 0 bis 100 % der Runde.
        raster = np.linspace(0.0, 1.0, PUNKTE, endpoint=False)
        def r(name, faktor=1.0):
            return np.interp(raster, pct, d[name][s].astype("f8")) * faktor
        kanaele = {
            "t": np.interp(raster, pct, tt) - zeiten[k],          # Zeit seit Rundenbeginn in s
            "speed": r("Speed", 3.6),                              # m/s -> km/h
            "gas": r("Throttle", 100.0),                           # 0..1 -> %
            "bremse": r("Brake", 100.0),
            "gang": np.round(r("Gear")),
            "rpm": r("RPM"),
            "lenkung": r("SteeringWheelAngle", 57.29578),          # rad -> Grad
            "lat": r("Lat"),
            "lon": r("Lon"),
        }
        runden.append({
            "nummer": int(d["Lap"][a]),
            "zeit": round(zeit, 3),
            "gueltig": grund == "",
            "grund": grund,
            "vmax": round(float(np.max(d["Speed"][a:b])) * 3.6, 1),
            "sprit": round(float(d["FuelLevel"][a] - d["FuelLevel"][b]), 2),
            "kanaele": kanaele,
        })
    return runden


# Alles zusammen: Datei -> (Session-Angaben, Liste der Runden).
def datei_auswerten(pfad):
    kopf = kopf_lesen(pfad)
    session = session_lesen(kopf["info"])
    session["datum"] = datetime.fromtimestamp(kopf["start"]).strftime("%Y-%m-%d %H:%M") if kopf["start"] > 0 else ""
    d = kanaele_lesen(pfad, kopf)
    runden = runden_bauen(d, kopf["takt"])
    # memmap schließen, damit die Datei danach gelöscht werden kann (wichtig unter Windows).
    del d
    return session, runden
