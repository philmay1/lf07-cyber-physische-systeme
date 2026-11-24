<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 06 Dynamische Zutrittskontrolle

Gleicher Aufbau wie Projekt 05, aber die PIN wird gegen einen Argon2id-Prüfwert in MariaDB geprüft. Ist die Datenbank weg, die Tür unbekannt oder der Prüfwert kaputt, bleibt die Tür zu (fail closed).

## Aufbau

Wie [Projekt 05](../05-lokale-zutrittskontrolle/). Zusätzlich MariaDB auf dem Pi.

## Starten

```bash
cd projekte/06-dynamische-zutrittskontrolle
bash einrichten.sh            # einmalig: MariaDB, Tabelle, Konten, /etc/sentinel/*.env
python3 pin_setzen.py         # Tür-PIN verdeckt eingeben, nur der Hash wird gespeichert
python3 zutritt_dynamisch.py  # oder mit --mqtt
```

## So funktioniert es

- Tabelle `access_doors` mit `door_id VARCHAR(32) PRIMARY KEY` und `door_code_hash VARCHAR(255) NOT NULL`. Eine PIN-Spalte gibt es nicht.
- Zwei Datenbankkonten nach dem Prinzip der Minimalrechte: `sentinel_access` darf nur `SELECT` (Laufzeit), `sentinel_admin` darf `SELECT`, `INSERT`, `UPDATE` (nur für `pin_setzen.py`). Kein Konto darf löschen oder die Tabelle ändern.
- Die Zugangsdaten erzeugt `einrichten.sh` zufällig und legt sie in `/etc/sentinel/access.env` und `admin.env` ab, mit chmod 600 und außerhalb des Repos.
- SQL nur mit Parameterbindung (`WHERE door_id = %s`), nie mit zusammengesetztem Text. `door_id` wird vorher auf das Format `[a-z0-9-]{1,32}` geprüft.
- `argon2-cffi` erzeugt den Prüfwert mit zufälligem Salt. Der Salt steckt im gespeicherten String, deshalb braucht es keine eigene Salt-Spalte.

## Tests

Automatisch auf dem Pi: `test_zutritt_dynamisch.py`: 16 Prüfungen, davon 11 ohne Datenbank (Argon2, fail closed, SQL-Injection-Versuch) und 5 mit der echten MariaDB auf dem Pi (Roundtrip, richtig/falsch, unbekannte Tür, Laufzeitkonto darf nicht schreiben). Alle grün.

Mit echten Bauteilen (noch offen):

| Test | Erwartet | Ergebnis |
|---|---|:-:|
| richtige PIN | Tür öffnet wie in Projekt 05 | ⬜ |
| falsche PIN | rot, keine Bewegung | ⬜ |
| `sudo systemctl stop mariadb`, PIN tippen | technischer Fehler, Tür bleibt zu | ⬜ |
| `door_id` in `sentinel.ini` leeren | Start wird abgelehnt | ⬜ |

## Dateien

| Datei | Aufgabe |
|---|---|
| [`zutritt_dynamisch.py`](zutritt_dynamisch.py) | Programm mit Prüfung gegen MariaDB |
| [`db_adapter.py`](db_adapter.py) | Datenbankzugriff, nur Parameterbindung |
| [`pin_setzen.py`](pin_setzen.py) | PIN verdeckt eingeben, Argon2id-Hash speichern |
| [`schema.sql`](schema.sql) | Datenbank und Tabelle |
| [`einrichten.sh`](einrichten.sh) | MariaDB, Konten und Zugangsdaten einrichten |
| [`sentinel.ini`](sentinel.ini) | nicht geheime Konfiguration (`door_id`) |
| [`test_zutritt_dynamisch.py`](test_zutritt_dynamisch.py) | automatischer Test |

Jede Code-Zeile hat einen deutschen Kommentar, der erklärt, was sie tut und warum sie da ist.

## Grenzen

Der Test legt eine eigene Tür `testtuer` an, damit `door01` unverändert bleibt. Wer root auf dem Pi ist, kann die env-Dateien lesen. Für mehrere Benutzer und Rollen bräuchte es eine weitere Tabelle.
