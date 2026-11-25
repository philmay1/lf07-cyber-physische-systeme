#!/bin/bash
# Startet SENTINEL Funk auf dem Pi: Logger, Brücke und Web-Board im Hintergrund,
# danach das Board als Fenster (z. B. für RealVNC Viewer oder den Beamer).
#
#   bash funk.sh einrichten   einmalig: Pakete, Schlüssel, abgesicherter Broker, Desktop-Symbol
#   bash funk.sh          alles starten und Board öffnen
#   bash funk.sh neu      wie oben, vorher alle alten Events löschen
#   bash funk.sh stopp    alles beenden
#   bash funk.sh status   zeigen, was läuft
#
# Absicherung (Tag 8):
#   bash funk.sh schluessel   .env + .env.password anlegen, Broker auf Login und Rechte umstellen
#   bash funk.sh angriff      Angriffstest: wehrt der Broker alles ab, was er soll?
#   bash funk.sh waechter     Commit-Wächter einschalten (stoppt Commits mit Passwörtern)
#   bash funk.sh notebook     Zugang fürs Notebook nach ~/funk-notebook (nur Sender-Passwort)
#   bash funk.sh offen        Notfall: Broker wieder ohne Login (wie Tag 5)

# In den Ordner dieses Skripts wechseln, damit alle Dateien gefunden werden.
cd "$(dirname "$(readlink -f "$0")")"

# Die drei Hintergrund-Programme dieser Übung.
PROGRAMME="mqtt_logger.py zutritt_bruecke.py funk_web.py"

# Beendet ein Programm, falls es läuft. [p] verhindert, dass pkill sich selbst findet.
stoppen() {
    pkill -f "[p]ython3 -u $1" && echo "gestoppt: $1"
}

# Startet ein Programm im Hintergrund, falls es noch nicht läuft. Ausgaben landen in /tmp.
starten() {
    if pgrep -f "[p]ython3 -u $1" > /dev/null; then
        echo "läuft schon: $1"
    else
        # setsid + nohup: läuft weiter, auch wenn das Terminal zugeht.
        # -u: Ausgaben sofort ins Log schreiben (sonst puffert Python sie).
        setsid nohup python3 -u $1 $2 > "/tmp/${1%.py}.log" 2>&1 < /dev/null &
        echo "gestartet: $1  (Log: /tmp/${1%.py}.log)"
    fi
}

# Was soll passieren?
case "$1" in
    # Alles beenden.
    stopp)
        for p in $PROGRAMME; do stoppen $p; done
        exit 0 ;;
    # Zeigen, was läuft, und ob Mosquitto aktiv ist.
    status)
        echo "Mosquitto: $(systemctl is-active mosquitto)"
        for p in $PROGRAMME; do pgrep -f "[p]ython3 -u $p" > /dev/null && echo "läuft: $p" || echo "aus:   $p"; done
        echo "Events in mqtt.db: $(python3 -c 'import funk_db; print(funk_db.anzahl(funk_db.verbinden()))')"
        exit 0 ;;
    # Einmalig: Pakete installieren, Broker absichern, Desktop-Symbol anlegen.
    einrichten)
        # Broker, Kommandozeilen-Werkzeuge, Python-Bibliotheken (inkl. python-dotenv), sqlite3, Emoji-Schrift.
        sudo apt-get install -y mosquitto mosquitto-clients python3-paho-mqtt python3-qrcode python3-dotenv sqlite3 fonts-noto-color-emoji
        # Schlüssel erzeugen und Mosquitto mit Login und Rechten starten.
        python3 funk_sicherheit.py schluessel && sudo python3 funk_sicherheit.py broker || exit 1
        # Commit-Wächter im Repo einschalten.
        git config core.hooksPath .githooks
        # Desktop-Symbol, das dieses Skript startet.
        printf "[Desktop Entry]\nType=Application\nName=SENTINEL Funk\nExec=bash $PWD/funk.sh\nIcon=network-wireless\nTerminal=false\n" \
            > ~/Desktop/FUNK.desktop
        chmod +x ~/Desktop/FUNK.desktop
        echo "Eingerichtet. Start: Doppelklick auf 'SENTINEL Funk' oder  bash funk.sh"
        exit 0 ;;
    # Schlüssel anlegen (falls nicht da) und Broker absichern. Danach die Programme stoppen,
    # damit sie beim nächsten Start die Passwörter lesen.
    schluessel)
        python3 funk_sicherheit.py schluessel && sudo python3 funk_sicherheit.py broker || exit 1
        for p in $PROGRAMME; do stoppen $p; done
        echo "Neu starten mit:  bash funk.sh"
        exit 0 ;;
    # Angriffstest gegen Broker und Repo.
    angriff)
        python3 angriff.py
        exit $? ;;
    # Commit-Wächter für dieses Repo einschalten (Git nimmt dann .githooks/pre-commit).
    waechter)
        git config core.hooksPath .githooks
        echo "Commit-Wächter an: $(git config core.hooksPath)"
        exit 0 ;;
    # Zugang fürs Notebook: .env mit der IP des Pi, .env.password nur mit dem Sender-Passwort.
    notebook)
        python3 funk_sicherheit.py notebook ~/funk-notebook --host "$(hostname -I | awk '{print $1}')"
        exit $? ;;
    # Notfall: zurück zum offenen Broker ohne Login.
    offen)
        sudo python3 funk_sicherheit.py offen
        exit $? ;;
    # Frisch anfangen: Logger neu starten und dabei die Tabelle leeren.
    neu)
        stoppen mqtt_logger.py
        sleep 1
        starten mqtt_logger.py --neu ;;
esac

# Mosquitto muss laufen (Systemdienst). Falls nicht: starten.
systemctl is-active --quiet mosquitto || sudo systemctl start mosquitto

# Die drei Programme starten (wenn sie nicht schon laufen).
for p in $PROGRAMME; do starten $p; done

# Kurz warten, bis der Webserver bereit ist.
sleep 2

# Board als App-Fenster ohne Adressleiste öffnen, über den ganzen Bildschirm (1920 x 1080).
chromium-browser --app=http://localhost:${FUNK_PORT:-5050} --window-position=0,0 --window-size=1920,1040 \
    --autoplay-policy=no-user-gesture-required > /dev/null 2>&1 &

# Adresse für die Handys anzeigen.
echo "Board offen. Handys: $(curl -s localhost:${FUNK_PORT:-5050}/api/info | python3 -c 'import sys, json; print(json.load(sys.stdin)["handy_url"])')"
