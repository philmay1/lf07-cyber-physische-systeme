#!/bin/bash
# Startet die Vorführung auf dem Pi-Desktop (z. B. über RealVNC Viewer):
# Dashboard links groß, Eingabe-Fenster rechts daneben. Tippen geht über die Tastatur.
#
#   bash vorfuehrung.sh einrichten   einmalig: Desktop-Symbol + Fensterregel anlegen
#   bash vorfuehrung.sh              Vorführung starten (oder Doppelklick auf das Desktop-Symbol)

# In den Ordner dieses Skripts wechseln, damit alle Dateien gefunden werden.
cd "$(dirname "$(readlink -f "$0")")"

# ---------- einmalige Einrichtung ----------
if [ "$1" = "einrichten" ]; then
    # Desktop-Symbol "SENTINEL Vorführung" anlegen, das dieses Skript startet.
    cat > ~/Desktop/SENTINEL.desktop <<EOF
[Desktop Entry]
Type=Application
Name=SENTINEL Vorführung
Comment=Zutrittskontrolle: Dashboard und Eingabe öffnen
Exec=bash $PWD/vorfuehrung.sh
Icon=security-high
Terminal=false
EOF
    # Symbol ausführbar machen.
    chmod +x ~/Desktop/SENTINEL.desktop
    # Dateimanager soll Desktop-Symbole ohne Rückfrage starten (quick_exec=1).
    mkdir -p ~/.config/libfm
    [ -f ~/.config/libfm/libfm.conf ] || cp /etc/xdg/libfm/libfm.conf ~/.config/libfm/libfm.conf
    grep -q "^quick_exec" ~/.config/libfm/libfm.conf \
        && sed -i "s/^quick_exec=.*/quick_exec=1/" ~/.config/libfm/libfm.conf \
        || sed -i "/^\[config\]/a quick_exec=1" ~/.config/libfm/libfm.conf
    # Fensterregel für den Fenstermanager openbox: Eingabe-Fenster rechts oben, immer im Vordergrund.
    regel=~/.config/openbox/lxde-pi-rc.xml
    if ! grep -q "SENTINEL Eingabe" "$regel" 2>/dev/null; then
        # Eigene Kopie der Systemeinstellung anlegen (falls noch keine da ist).
        mkdir -p ~/.config/openbox
        [ -f "$regel" ] || cp /etc/xdg/openbox/lxde-pi-rc.xml "$regel"
        # Die Regel vor dem Ende des Abschnitts <applications> einfügen.
        sed -i 's#  </applications>#    <application title="SENTINEL Eingabe">\n      <position force="yes"><x>1295</x><y>45</y></position>\n      <focus>yes</focus>\n      <layer>above</layer>\n    </application>\n  </applications>#' "$regel"
        # openbox die neue Einstellung neu laden lassen.
        openbox --reconfigure
    fi
    echo "Eingerichtet. Jetzt auf dem Desktop 'SENTINEL Vorführung' doppelklicken."
    exit 0
fi

# ---------- Vorführung starten ----------
# Läuft das Dashboard noch nicht? Dann im Hintergrund starten (setsid: läuft weiter, wenn das Fenster zugeht).
if ! pgrep -f "python3 dashboard.py" > /dev/null; then
    setsid nohup python3 dashboard.py > /tmp/dashboard.log 2>&1 < /dev/null &
    # Zwei Sekunden warten, bis der Webserver bereit ist.
    sleep 2
fi

# Dashboard als App-Fenster ohne Adressleiste öffnen: links, 1280 x 1040 Pixel.
# --autoplay-policy erlaubt Ton ohne vorherigen Klick (der Knopf "Ton aktivieren" bleibt trotzdem nötig).
chromium-browser --app=http://localhost:5000 --window-position=0,0 --window-size=1280,1040 \
    --autoplay-policy=no-user-gesture-required > /dev/null 2>&1 &

# Kurz warten, damit das Terminal danach oben liegt und die Tastatur-Eingaben bekommt.
sleep 3

# Eingabe-Fenster öffnen: hier läuft die Zutrittskontrolle im Tastatur-Modus.
# Gibt es ein Keypad, statt "--tastatur" einfach nichts angeben.
lxterminal --title="SENTINEL Eingabe" --geometry=70x30 \
    -e bash -c 'python3 zutritt.py --tastatur; echo; read -p "Enter zum Schließen"' &
