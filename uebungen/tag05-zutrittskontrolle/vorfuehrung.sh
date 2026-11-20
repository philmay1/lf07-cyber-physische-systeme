#!/bin/bash
# Startet die Vorführung auf dem Pi-Desktop (z. B. über RealVNC Viewer):
# Dashboard links groß, Eingabe-Fenster rechts daneben. Tippen geht über die Tastatur.
# Aufruf per Doppelklick auf "SENTINEL Vorführung" auf dem Desktop oder: bash vorfuehrung.sh

# In den Ordner dieses Skripts wechseln, damit alle Dateien gefunden werden.
cd "$(dirname "$(readlink -f "$0")")"

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
