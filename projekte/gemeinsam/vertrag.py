"""SENTINEL-Schnittstellenvertrag 1.0.0 (Topic-/Payload-Katalog von Tag 3, AB3).

Baut Nachrichten nach dem Katalog und prüft sie, bevor sie gesendet werden,
und noch einmal beim Empfänger. Eine Nachricht, die nicht passt, wird nie gesendet.
"""
import json                              # wandelt Python-Wörterbücher in JSON-Text um und zurück
import re                                # reguläre Ausdrücke, um Topic und Zeitformat zu prüfen
import uuid                              # erzeugt die eindeutige message_id (UUID v4)
from datetime import datetime, timezone  # aktuelle Uhrzeit in UTC für den Zeitstempel

SCHEMA_VERSION = "1.0.0"                 # Version des Vertrags, steht in jeder Nachricht
STANDORT = "lab01"                       # verbindlicher Standort laut Katalog

# Erlaubte Geräte je Modul, genau wie im Katalog (3.3)
GERAETE = {                              # Modul -> erlaubte device_id
    "material": "station01",             # Materialservice
    "safety": "chamber01",               # Personensicherheit (Klimaprüfraum)
    "access": "door01",                  # Zutrittskontrolle
    "environment": "rack01",             # Umgebungsüberwachung
    "transport": "box001",               # Transportüberwachung
}

# QoS und Retain je Nachrichtentyp (3.7): Ereignisse nie retained, Status immer retained
UEBERTRAGUNG = {                         # Nachrichtentyp -> (QoS, retain)
    "request": (1, False),               # Materialanforderung: darf nicht verloren gehen
    "event": (1, False),                 # Zutrittsereignis
    "alarm": (1, False),                 # Alarm: mindestens einmal zustellen
    "telemetry": (0, False),             # Messwerte: ein verlorener Wert ist verkraftbar
    "status": (1, True),                 # Status: neuer Empfänger sieht sofort den letzten Stand
}

PFLICHTFELDER = ("device_id", "event_type", "timestamp", "status", "message_id", "schema_version")  # 3.5
ERLAUBTE_STATUS = {"active", "normal", "warning", "alarm", "online", "offline", "acknowledged"}      # 3.5

# Modulspezifische Pflichtfelder (3.6): (Modul, Typ) -> {Feld: erlaubter Python-Typ}
ZUSATZ = {                                           # nur diese Kombinationen haben Extra-Pflichtfelder
    ("material", "request"): {"request_count": int},  # angeforderte Stückzahl
    ("safety", "alarm"): {"motion_detected": bool},   # wurde Bewegung erkannt?
    ("access", "event"): {"access_result": str},      # granted oder denied, nie die PIN
}

TOPIC_MUSTER = re.compile(r"^sentinel/lab01/(material|safety|access|environment|transport)/[a-z0-9-]+/(request|event|telemetry|alarm|status|cmd)$")  # 3.3
ZEIT_MUSTER = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$")  # RFC 3339 in UTC mit Z


class VertragsFehler(ValueError):        # eigene Fehlerklasse, damit man Vertragsfehler gezielt abfangen kann
    """Die Nachricht verletzt den Schnittstellenvertrag."""


def topic(modul, typ):                   # baut das vollständige Topic aus Modul und Nachrichtentyp
    return f"sentinel/{STANDORT}/{modul}/{GERAETE[modul]}/{typ}"  # z. B. sentinel/lab01/access/door01/event


def utc_jetzt():                         # Zeitstempel im Vertragsformat
    jetzt = datetime.now(timezone.utc)   # aktuelle Zeit in UTC, nie Ortszeit (Vertrag 3.5)
    return jetzt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{jetzt.microsecond // 1000:03d}Z"  # Millisekunden + Z


def nachricht(modul, event_type, status, **zusatz):  # baut ein vollständiges Payload-Wörterbuch
    daten = {                                         # die sechs Pflichtfelder in fester Reihenfolge
        "device_id": GERAETE[modul],                  # passt automatisch zum Gerät im Topic
        "event_type": event_type,                     # fachliche Art, z. B. material_request
        "timestamp": utc_jetzt(),                     # Erzeugungszeit beim Sender
        "status": status,                             # z. B. active, alarm, online
        "message_id": str(uuid.uuid4()),              # neue UUID je Ereignis, für Duplikaterkennung
        "schema_version": SCHEMA_VERSION,             # damit der Empfänger die Version prüfen kann
    }
    daten.update(zusatz)                              # modulspezifische Felder anhängen
    return daten                                      # fertiges Wörterbuch zurückgeben


def pruefen(topic_text, daten):                       # prüft Topic und Payload gegen den Vertrag
    if not TOPIC_MUSTER.match(topic_text):            # Topic-Aufbau und Kleinschreibung
        raise VertragsFehler(f"Topic passt nicht zum Katalog: {topic_text}")  # Abbruch: Topic falsch
    _, _, modul, geraet, typ = topic_text.split("/")  # Topic in seine fünf Ebenen zerlegen
    if GERAETE.get(modul) != geraet:                  # Gerät muss zum Modul gehören
        raise VertragsFehler(f"Gerät {geraet} gehört nicht zu Modul {modul}")  # Abbruch: Gerät falsch
    for feld in PFLICHTFELDER:                        # jedes Pflichtfeld muss da sein ...
        if not isinstance(daten.get(feld), str) or not daten[feld]:  # ... und ein nicht leerer Text sein
            raise VertragsFehler(f"Pflichtfeld fehlt oder ist kein Text: {feld}")  # Abbruch: Pflichtfeld fehlt
    if daten["device_id"] != geraet:                  # device_id und Topic müssen zusammenpassen
        raise VertragsFehler("device_id passt nicht zum Topic")  # Abbruch: Topic und Payload widersprechen sich
    if daten["status"] not in ERLAUBTE_STATUS:        # nur freigegebene Statuswerte
        raise VertragsFehler(f"unbekannter Status: {daten['status']}")  # Abbruch: Status unbekannt
    if not ZEIT_MUSTER.match(daten["timestamp"]):     # Zeitformat RFC 3339 mit Z
        raise VertragsFehler("Zeitstempel ist nicht UTC im Format ...Z")  # Abbruch: Zeitformat falsch
    if daten["schema_version"].split(".")[0] != SCHEMA_VERSION.split(".")[0]:  # gleiche Major-Version
        raise VertragsFehler("inkompatible Schema-Version")  # Abbruch: andere Major-Version
    uuid.UUID(daten["message_id"])                    # wirft ValueError, wenn keine gültige UUID
    for feld, art in ZUSATZ.get((modul, typ), {}).items():  # modulspezifische Pflichtfelder
        wert = daten.get(feld)                        # Wert holen (None, wenn er fehlt)
        if art is int and (isinstance(wert, bool) or not isinstance(wert, int)):  # bool ist in Python auch int
            raise VertragsFehler(f"{feld} muss eine Ganzzahl sein")  # Abbruch: keine Ganzzahl
        if art is not int and not isinstance(wert, art):  # alle anderen Typen direkt prüfen
            raise VertragsFehler(f"{feld} hat den falschen Typ")  # Abbruch: falscher Typ
    if "pin" in {k.lower() for k in daten}:           # Sicherheitsregel: eine PIN hat im Payload nichts verloren
        raise VertragsFehler("PIN darf nie übertragen werden")  # Abbruch: PIN gefunden
    return modul, typ                                 # Modul und Typ zurückgeben, falls der Aufrufer sie braucht


def als_json(topic_text, daten):                      # prüft und serialisiert in einem Schritt
    pruefen(topic_text, daten)                        # erst prüfen: ungültig wird nie gesendet
    return json.dumps(daten, ensure_ascii=False, allow_nan=False)  # NaN ist kein gültiges JSON


def aus_json(topic_text, roh):                        # Empfängerseite: Bytes -> geprüftes Wörterbuch
    daten = json.loads(roh.decode("utf-8"))           # UTF-8 dekodieren, JSON parsen (wirft bei Müll)
    if not isinstance(daten, dict):                   # ein JSON-Array oder eine Zahl ist keine Nachricht
        raise VertragsFehler("Payload ist kein JSON-Objekt")  # Abbruch: kein Objekt
    pruefen(topic_text, daten)                        # gleiche Regeln wie beim Sender
    return daten                                      # geprüfte Daten zurückgeben
