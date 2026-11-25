#!/bin/bash
# Richtet das Telemetrie-Labor auf dem Pi ein und startet es als Dienst (startet auch nach jedem Neustart).
#
#   bash einrichten.sh            Pakete, .env, systemd-Dienst
#   bash einrichten.sh status     läuft der Dienst? letzte Log-Zeilen
#   bash einrichten.sh entfernen  Dienst stoppen und austragen (Daten bleiben)

# In den Ordner dieses Skripts wechseln.
cd "$(dirname "$(readlink -f "$0")")"
DIENST=telemetrie-labor

case "$1" in
    status)
        systemctl --no-pager status $DIENST | head -5
        journalctl -u $DIENST -n 8 --no-pager
        exit 0 ;;
    entfernen)
        sudo systemctl disable --now $DIENST
        sudo rm -f /etc/systemd/system/$DIENST.service
        sudo systemctl daemon-reload
        echo "Dienst entfernt. labor.db bleibt erhalten."
        exit 0 ;;
esac

# 1. Pakete: numpy (Rechnen mit Spalten), Flask (Webserver), python-dotenv (.env lesen).
sudo apt-get install -y python3-numpy python3-flask python3-dotenv

# 2. Einstellungen anlegen, falls es noch keine gibt (Vorlage: .env.example).
[ -f .env ] || cp .env.example .env

# ======== SCHRITT 1 von 21: Das Labor wird zum Dienst ========
# systemd ist der Dienst-Verwalter von Linux. Er startet labor.py beim Hochfahren des Pi und nach einem Absturz neu.
# 3. systemd-Dienst schreiben: läuft als dieser Benutzer, in diesem Ordner, startet bei Fehlern neu.
sudo tee /etc/systemd/system/$DIENST.service > /dev/null <<EOF
[Unit]
Description=Telemetrie-Labor (iRacing-Auswertung im Browser)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$PWD
ExecStart=/usr/bin/python3 -u $PWD/labor.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 4. Dienst laden, beim Booten starten und jetzt sofort starten.
sudo systemctl daemon-reload
sudo systemctl enable --now $DIENST
sleep 2
systemctl is-active --quiet $DIENST && echo "Telemetrie-Labor läuft: http://$(hostname -I | awk '{print $1}'):$(grep -oP '^LABOR_PORT=\K.*' .env || echo 5080)"

# Hinweis zum Passwort.
grep -q LABOR_PASSWORT_HASH .env.password 2>/dev/null || \
    echo "Noch kein Passwort: Hochladen geht nur am Pi selbst. Setzen mit:  python3 labor.py passwort  (danach: sudo systemctl restart $DIENST)"
