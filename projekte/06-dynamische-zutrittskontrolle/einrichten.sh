#!/bin/bash
# SENTINEL Projekt 06: MariaDB einmalig einrichten (Tag 6, AB1 bis AB3).
# Legt Datenbank, Tabelle und zwei Datenbank-Benutzer mit Minimalrechten an:
#   sentinel_access_app   darf nur SELECT auf access_doors   (Laufzeit: Zutrittskontrolle)
#   sentinel_admin        darf SELECT, INSERT, UPDATE         (nur zum Setzen der Tür-PIN)
# Die Passwörter werden zufällig erzeugt und landen in /etc/sentinel/*.env (chmod 600),
# also außerhalb des Repositorys. Aufruf auf dem Pi:  bash einrichten.sh
set -euo pipefail                                   # bei jedem Fehler sofort abbrechen

HIER="$(cd "$(dirname "$0")" && pwd)"               # Ordner dieses Skripts, damit schema.sql gefunden wird
BENUTZER="$(id -un)"                                # Linux-Benutzer, der die Programme startet (z. B. phil)

sudo apt-get install -y -q mariadb-server python3-argon2 >/dev/null   # Datenbank und Argon2 (idempotent)
python3 -c "import mysql.connector" 2>/dev/null || pip3 install --user mysql-connector-python==8.0.33  # Python-Connector
sudo systemctl enable --now mariadb                 # Dienst starten und beim Booten automatisch starten

sudo mysql < "$HIER/schema.sql"                     # Datenbank und Tabelle anlegen (als Datenbank-Root über den Unix-Socket)

sudo mkdir -p /etc/sentinel                         # Ablage für Zugangsdaten außerhalb des Repos
for ROLLE in access admin; do                       # zwei Konten: Laufzeit und Verwaltung
    DATEI="/etc/sentinel/$ROLLE.env"                # Zieldatei für dieses Konto
    if sudo test -f "$DATEI"; then                  # schon eingerichtet?
        echo "$DATEI existiert bereits, bleibt unverändert"   # Passwort nicht überschreiben
        continue                                    # nächstes Konto
    fi
    PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"   # starkes Zufallspasswort
    if [ "$ROLLE" = access ]; then                  # Laufzeitkonto
        RECHTE="SELECT"                             # nur lesen (AB1, Minimalrecht)
    else                                            # Verwaltungskonto
        RECHTE="SELECT, INSERT, UPDATE"             # Prüfwert anlegen und ersetzen, kein DELETE, kein DROP
    fi
    sudo mysql -e "CREATE OR REPLACE USER 'sentinel_$ROLLE'@'localhost' IDENTIFIED BY '$PASS'; GRANT $RECHTE ON sentinel.access_doors TO 'sentinel_$ROLLE'@'localhost'; FLUSH PRIVILEGES;"   # Konto und Rechte
    printf 'SENTINEL_DB_HOST=localhost\nSENTINEL_DB_NAME=sentinel\nSENTINEL_DB_USER=sentinel_%s\nSENTINEL_DB_PASSWORD=%s\n' "$ROLLE" "$PASS" | sudo tee "$DATEI" >/dev/null   # Zugangsdaten schreiben, nicht anzeigen
    sudo chown "$BENUTZER":"$BENUTZER" "$DATEI"     # nur dieser Benutzer ...
    sudo chmod 600 "$DATEI"                         # ... darf die Datei lesen
    echo "$DATEI angelegt (chmod 600)"              # Rückmeldung ohne Passwort
done

echo "Fertig. Jetzt die Tür-PIN setzen:  python3 $HIER/pin_setzen.py"   # nächster Schritt
