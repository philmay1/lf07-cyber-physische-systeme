<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# 06 Dynamic access control

Same setup as project 05, but the PIN is checked against an Argon2id hash in MariaDB. If the database is down, the door is unknown or the hash is broken, the door stays locked (fail closed).

## Wiring

Same as [project 05](../05-lokale-zutrittskontrolle/). Plus MariaDB on the Pi.

## Run

```bash
cd projekte/06-dynamische-zutrittskontrolle
bash einrichten.sh            # einmalig: MariaDB, Tabelle, Konten, /etc/sentinel/*.env
python3 pin_setzen.py         # Tür-PIN verdeckt eingeben, nur der Hash wird gespeichert
python3 zutritt_dynamisch.py  # oder mit --mqtt
```

## How it works

- Table `access_doors` with `door_id VARCHAR(32) PRIMARY KEY` and `door_code_hash VARCHAR(255) NOT NULL`. There is no PIN column.
- Two database accounts following least privilege: `sentinel_access` may only `SELECT` (runtime), `sentinel_admin` may `SELECT`, `INSERT`, `UPDATE` (only for `pin_setzen.py`). No account can delete or alter the table.
- `einrichten.sh` generates random credentials and stores them in `/etc/sentinel/access.env` and `admin.env`, chmod 600, outside the repo.
- SQL only with parameter binding (`WHERE door_id = %s`), never by building strings. `door_id` is checked against `[a-z0-9-]{1,32}` first.
- `argon2-cffi` creates the hash with a random salt. The salt is part of the stored string, so no separate salt column is needed.

## Tests

Automatic on the Pi: `test_zutritt_dynamisch.py`: 16 checks, 11 without database (Argon2, fail closed, SQL injection attempt) and 5 against the real MariaDB on the Pi (roundtrip, right/wrong, unknown door, runtime account cannot write). All passing.

With real hardware (still open):

| Test | Expected | Result |
|---|---|:-:|
| richtige PIN | Tür öffnet wie in Projekt 05 | ⬜ |
| falsche PIN | rot, keine Bewegung | ⬜ |
| `sudo systemctl stop mariadb`, PIN tippen | technischer Fehler, Tür bleibt zu | ⬜ |
| `door_id` in `sentinel.ini` leeren | Start wird abgelehnt | ⬜ |

## Files

| File | Purpose |
|---|---|
| [`zutritt_dynamisch.py`](zutritt_dynamisch.py) | Programm mit Prüfung gegen MariaDB |
| [`db_adapter.py`](db_adapter.py) | Datenbankzugriff, nur Parameterbindung |
| [`pin_setzen.py`](pin_setzen.py) | PIN verdeckt eingeben, Argon2id-Hash speichern |
| [`schema.sql`](schema.sql) | Datenbank und Tabelle |
| [`einrichten.sh`](einrichten.sh) | MariaDB, Konten und Zugangsdaten einrichten |
| [`sentinel.ini`](sentinel.ini) | nicht geheime Konfiguration (`door_id`) |
| [`test_zutritt_dynamisch.py`](test_zutritt_dynamisch.py) | automatischer Test |

Every line of code has a German comment explaining what it does and why it is there.

## Limits

The test creates its own door `testtuer` so `door01` stays untouched. Anyone with root on the Pi can read the env files. Several users and roles would need another table.
