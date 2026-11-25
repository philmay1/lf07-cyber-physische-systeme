<p align="right"><a href="README.md">English</a> · <a href="README.de.md">Deutsch</a></p>

# Übung Tag 5: SENTINEL Funk (MQTT, Mosquitto, SQLite)

![Live-Board am Beamer: Sender, Broker, Datenbank](bilder/board_live.jpg)

## Aufgabe (Wortlaut vom Dozenten)

> Ein Sender sendet Daten (was auch immer, physische Daten, Eingabe des Users etc.). Mosquitto empfängt das Event von seinem Client (es reicht ein Client, aber gerne mehr). Eine Funktion macht eine Subscription auf dieses Topic und schreibt den Wert und die Zeit in eine DB. Bitte 10 bis 20 Events produzieren, gerne mehr.

## Lösung in einem Satz

Mehrere Clients schicken Events an den Broker Mosquitto auf dem Pi. Die Funktion `beim_empfang()` in [`mqtt_logger.py`](mqtt_logger.py) hat `lf07/#` abonniert und schreibt jedes Event mit Zeit, Topic, Sender und Wert in die SQLite-Datei `mqtt.db`.

## Wie MQTT hier funktioniert

MQTT arbeitet nach dem Prinzip Publish/Subscribe. Ein Sender (Publisher) schickt eine Nachricht nicht direkt an einen Empfänger. Er gibt sie mit einem Topic beim Broker ab, so wie man einen Brief mit Adresse bei der Post einwirft. Der Broker reicht sie an alle weiter, die dieses Topic abonniert haben (Subscriber). Sender und Empfänger kennen sich nicht. Deshalb kann man jederzeit weitere Sender oder Empfänger dazunehmen, ohne etwas umzubauen.

```mermaid
flowchart LR
    K["Pi-Keypad<br/>zutritt.py"] -->|lf07/keypad/versuch| B(("Mosquitto<br/>:1883 / :9001"))
    S["Pi-Sensor<br/>CPU-Temperatur"] -->|lf07/sender/pi/cpu_temperatur| B
    N["Notebook<br/>sender.py"] -->|lf07/sender/&lt;name&gt;/temperatur| B
    H["Handys der Klasse<br/>handy.html"] -->|lf07/handy/&lt;name&gt;/knopf| B
    B -->|"Abo lf07/#"| L["mqtt_logger.py<br/>beim_empfang()"]
    L --> D[("mqtt.db<br/>Tabelle events")]
    B -->|lf07/zutritt/pin| Z["zutritt_bruecke.py"]
    Z --> ZD[("zutritt.db<br/>Sperre nach 3 Fehlern")]
    B -->|"Abo lf07/#"| W["Live-Board<br/>board.html"]
```

| Teil der Aufgabe | Umsetzung |
|---|---|
| Sender mit physischen Daten | `sender.py --cpu` liest die echte CPU-Temperatur des Pi |
| Sender mit Eingabe des Users | Keypad (oder Tastatur) über `zutritt.py`, Handyseite, `sender.py` zum Tippen |
| Broker | Mosquitto 2.0 auf dem Pi, Port 1883 (MQTT) und 9001 (MQTT über WebSocket für Browser) |
| Funktion mit Subscription | `beim_empfang()` in `mqtt_logger.py`, Abo auf `lf07/#` |
| Wert und Zeit in eine DB | Tabelle `events` in `mqtt.db` (SQLite) |
| 10 bis 20 Events | `sender.py --anzahl 20` erzeugt 20 auf einen Schlag, dazu jedes Handy |

`#` im Topic ist ein Platzhalter: `lf07/#` heißt "alles, was mit lf07/ beginnt". So fängt ein einziges Abo alle Sender ein.

## Die Tabelle

```sql
CREATE TABLE events (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,  -- laufende Nummer
    zeit   REAL    NOT NULL,                   -- Empfangszeit in Sekunden seit 1970
    topic  TEXT    NOT NULL,                   -- z. B. lf07/handy/lisa/knopf
    sender TEXT    NOT NULL DEFAULT '',        -- wer gesendet hat
    wert   TEXT    NOT NULL                    -- der Wert als Text
);
```

Die Zeit steht als Zahl in der Datenbank. Lesbar wird sie erst bei der Abfrage:

```bash
sqlite3 mqtt.db "SELECT id, datetime(zeit,'unixepoch','localtime'), topic, sender, wert FROM events ORDER BY id DESC LIMIT 20;"
```

## Der Wow-Teil

- **Live-Board** (`http://<Pi>:5050`): Jedes Event fliegt als leuchtendes Paket vom Sender zum Broker. Sobald der Logger es gespeichert hat, fliegt ein grünes Paket in die Datenbank-Tonne. Darunter läuft die echte Tabelle aus `mqtt.db` mit, samt der SQL-Abfrage. Bei 20 Events seit Start gibt es Konfetti und "20 EVENTS ✓".
- **Die Klasse macht mit:** Auf dem Board hängt ein QR-Code. Wer ihn scannt, wird mit dem Handy selbst zum MQTT-Client und kann Knöpfe drücken und einen Messwert schicken.
- **Knack den Tresor:** Auf dem Handy gibt es einen Ziffernblock. Die PIN geht per MQTT an die echte Zutrittskontrolle aus Tag 5. Nach drei falschen PINs sperrt SENTINEL. Das Board zeigt einen roten Alarm, das SENTINEL-Dashboard auf Port 5000 schaltet auf Lockdown, und läuft `zutritt.py`, geht am Pi die rote LED an.

## Vorführung

Einmalig auf dem Pi (Pakete, Mosquitto-Einstellung, Desktop-Symbol):

```bash
cd ~/lf07-cyber-physische-systeme/uebungen/tag05-mqtt
bash funk.sh einrichten
```

Vor der Vorführung:

1. `bash funk.sh neu` startet Logger, Brücke und Board mit leerer Tabelle. Alternativ Doppelklick auf "SENTINEL Funk" (dann ohne Leeren).
2. Am Board "Ton an" klicken, Board per RealVNC oder Beamer zeigen.
3. Die Klasse scannt den QR-Code. Handys und Pi müssen im selben WLAN sein.
4. Vom Notebook 20 Events nachschießen: `python sender.py --host <IP des Pi> --anzahl 20`
5. Echte Sensordaten: auf dem Pi `python3 sender.py --host localhost --cpu --anzahl 10`
6. Beweis aus der Datenbank: die `sqlite3`-Abfrage von oben im Terminal zeigen.

`bash funk.sh status` zeigt, was läuft und wie viele Events gespeichert sind. `bash funk.sh stopp` beendet alles.

## Auf dem Notebook

```powershell
pip install paho-mqtt python-dotenv
python sender.py --anzahl 20
```

Seit Tag 8 braucht der Sender einen Login. Auf dem Pi legt `bash funk.sh notebook` den Ordner `~/funk-notebook` mit `.env` (Adresse des Pi) und `.env.password` (nur das Sender-Passwort) an. Beide Dateien kommen per LocalSend neben `sender.py`, nie über GitHub.

## Dateien

| Datei | Aufgabe |
|---|---|
| [mqtt_logger.py](mqtt_logger.py) | Subscriber: `beim_empfang()` schreibt jedes Event in `mqtt.db` |
| [sender.py](sender.py) | Publisher für Pi und Notebook: Messreihe, CPU-Temperatur, Text |
| [zutritt_bruecke.py](zutritt_bruecke.py) | prüft PINs aus MQTT gegen `zutritt.db` und antwortet dem Handy |
| [funk_web.py](funk_web.py) | Flask auf Port 5050: liefert Board, Handyseite, QR-Code, Daten |
| [board.html](board.html) / [handy.html](handy.html) | Live-Board und Handyseite, beide selbst MQTT-Clients über WebSocket |
| [funk_db.py](funk_db.py) | gemeinsame Datenbank-Funktionen und MQTT-Client für paho 1.x und 2.x |
| [funk.sh](funk.sh) | einrichten, starten, stoppen, Status, Schlüssel, Angriffstest |
| [funk_sicherheit.py](funk_sicherheit.py) | Rollen, Zufallspasswörter, Mosquitto-Login und ACL (Tag 8) |
| [angriff.py](angriff.py) | Angriffstest gegen Broker und Repo (Tag 8) |
| [.env.example](.env.example) | Vorlage für `.env` und `.env.password` |
| [test_funk.py](test_funk.py) | 30 Prüfungen ohne Broker |
| static/mqtt.min.js | MQTT.js 4.3.7 für den Browser, liegt lokal, damit kein Internet nötig ist |

Außerdem meldet [`../tag05-zutrittskontrolle/zutritt.py`](../tag05-zutrittskontrolle/zutritt.py) jetzt jeden PIN-Versuch als `ok`, `falsch` oder `gesperrt` auf `lf07/keypad/versuch`. Die PIN selbst wird nie gesendet. Fehlt paho-mqtt oder läuft kein Broker, arbeitet die Zutrittskontrolle wie vorher.

![Handyseite](bilder/handy.jpg)

## Absicherung mit .env, .env.password und .gitignore (Tag 8)

An Tag 5 nahm der Broker jeden an: Wer im WLAN war, konnte alles mitlesen und unter jedem Namen senden. Seit Tag 8 braucht jedes Programm einen Login, und jede Rolle darf nur das, was sie für ihre Aufgabe braucht.

### Drei Dateien, drei Aufgaben

| Datei | Inhalt | Im Git? |
|---|---|:-:|
| `.env` | Einstellungen dieses Rechners: `MQTT_HOST`, `MQTT_PORT`, `MQTT_WS_PORT`, `FUNK_PORT` | nein |
| `.env.password` | nur die Passwörter, eine Zeile pro Rolle (`MQTT_PASS_LOGGER=...`), Rechte 600 | nein |
| [`.env.example`](.env.example) | dieselben Namen mit Platzhaltern, als Anleitung für andere | ja |
| [`../../.gitignore`](../../.gitignore) | sperrt `.env`, `*.env` und `.env.*`, lässt nur `.env.example` durch | ja |

Einstellungen und Passwörter liegen getrennt, weil man sie verschieden behandelt. Die `.env` darf man jemandem zeigen, wenn eine Verbindung nicht klappt. Die `.env.password` verlässt den Rechner nie, und das Notebook bekommt davon nur eine einzige Zeile.

Vor Tag 8 stand in der `.gitignore` schon `.env` und `*.env`. Eine Datei `.env.password` hätte das trotzdem nicht gesperrt, denn ihr Name endet auf `.password`. Erst die Zeile `.env.*` schließt diese Lücke. Prüfen lässt sich das mit `git check-ignore -v .env.password`.

### Wer darf was (ACL)

Die Rollen stehen an einer Stelle in [`funk_sicherheit.py`](funk_sicherheit.py). Daraus entstehen die Passwortdatei und die Rechte-Datei für Mosquitto.

| Rolle | Wer | darf lesen | darf senden |
|---|---|---|---|
| `logger` | `mqtt_logger.py` | `lf07/#` | nichts |
| `board` | Live-Board | Handy, Sender, Keypad, Antworten. **Keine PINs** | nichts |
| `bruecke` | `zutritt_bruecke.py` | `lf07/zutritt/pin` | `lf07/zutritt/antwort/#` |
| `keypad` | `zutritt.py` | nichts | `lf07/keypad/versuch` |
| `sender` | `sender.py` (Pi, Notebook) | nichts | `lf07/sender/#` |
| `handy` | Handyseite | Antworten | `lf07/handy/#`, `lf07/zutritt/pin` |

Board und Handy laufen im Browser. Alles, was dort ankommt, kann jeder Besucher im Quelltext sehen, also auch ihr Passwort. Deshalb bekommen genau diese beiden die schwächsten Rollen. Wer das Handy-Passwort abgreift, kann Knöpfe drücken und PINs raten (nach 3 Fehlern sperrt SENTINEL), aber keine Keypad-Meldung fälschen und nichts mitlesen.

### Das Passwort steht nie im Code

`funk_db.py`, `sender.py` und `zutritt.py` laden `.env` und `.env.password` mit python-dotenv und lesen dann `os.environ`. Fehlt ein Passwort, verbinden sie sich ohne Login. Ein abgesicherter Broker lehnt das ab, und das Programm sagt, was fehlt.

### Commit-Wächter

[`../../.githooks/geheimnis_waechter.py`](../../.githooks/geheimnis_waechter.py) läuft vor jedem Commit. Er stoppt den Commit, wenn eine Datei wie `.env` oder `.env.password` dabei ist, auch mit `git add -f`. Außerdem sucht er jeden Passwort-Wert aus den echten Geheimnis-Dateien in allen vorgemerkten Dateien. So fällt es auf, wenn jemand ein Passwort in den Code kopiert. Eingeschaltet wird er einmal pro Klon mit `git config core.hooksPath .githooks` (macht `bash funk.sh waechter`).

### Einrichten und vorführen

```bash
bash funk.sh schluessel    # .env + .env.password (Zufallspasswörter) anlegen, Broker mit Login + ACL starten
bash funk.sh waechter      # Commit-Wächter einschalten
bash funk.sh neu           # Logger, Brücke, Board starten
bash funk.sh angriff       # Angriffstest
bash funk.sh notebook      # Zugang fürs Notebook nach ~/funk-notebook (nur Sender-Passwort)
```

Der Angriffstest probiert zwölf Angriffe gegen den echten Broker und das Repo aus:

- anonym, mit falschem Passwort und mit `admin/admin` verbinden
- als Handy eine Keypad-Meldung fälschen, als Board senden, als Sender eine SENTINEL-Antwort fälschen
- als Board PINs mitlesen (Mosquitto bestätigt das Abo, liefert aber keine einzige Nachricht)
- `.env` und `.env.password` sind gesperrt, keine echte `.env` im Repo, `.env.password` hat Rechte 600
- ein Commit mit einem echten Passwort im Code

Vorher schickt er als Gegenprobe einen erlaubten Handy-Knopf, damit klar ist, dass der Broker überhaupt Nachrichten durchlässt. Ergebnis auf dem Pi: 12 von 12 abgewehrt.

Notfall in einer Vorführung: `bash funk.sh offen` stellt den Broker zurück auf den Stand von Tag 5.

## Getestet

- `python3 test_funk.py`: 30 von 30 Prüfungen bestanden, `test_zutritt.py` weiter grün.
- Tag 8 auf dem Pi: `bash funk.sh angriff` wehrt 12 von 12 Angriffen ab. Notebook-Sender mit Login sendet, ohne Login lehnt der Broker ab (Code 135). Board und Handy verbinden sich in Edge mit ihren Rollen.
- Live auf dem Pi mit Mosquitto 2.0.11: 20 Notebook-Werte, 3 CPU-Temperaturen, 3 falsche PINs mit Sperre und eine Keypad-Meldung, zusammen 30 Zeilen in `mqtt.db`.
- Handyseite in Edge mit Handygröße über WLAN: verbindet, sendet, bekommt die Sperr-Antwort.

## Grenzen

- Seit Tag 8 gibt es Login und Rechte, aber noch keine Verschlüsselung. Passwörter und Nachrichten gehen im Klartext durchs WLAN und lassen sich mit Wireshark mitlesen. Der nächste Schritt wäre TLS (Port 8883, für Browser `wss://`).
- Eine PIN vom Handy geht im Klartext über das WLAN. Die Datenbank speichert nur `PIN ****`, das Board zeigt sie nie. Deshalb dort nie die echte Admin-PIN eintippen.
- Manche Schul-WLANs trennen Geräte voneinander (Client-Isolation). Dann erreichen die Handys den Pi nicht. Notebook und Pi-Sender funktionieren trotzdem, wenn das Notebook per LAN oder Tailscale dran ist.
