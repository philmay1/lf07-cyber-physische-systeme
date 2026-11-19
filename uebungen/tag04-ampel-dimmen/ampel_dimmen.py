"""Übung Tag 4: Ampel dimmen mit PWM.

Die drei Autolampen leuchten nacheinander, jede schwächer als die davor:
rot 100 %, gelb 60 %, grün 20 %. Danach leuchten alle drei zusammen,
damit man die Stufen direkt nebeneinander vergleichen kann.
Beenden mit Strg+C, danach sind alle Lampen aus.

Schaltung: wie die Autoampel aus Tag 3, jede LED über 220 Ohm gegen GND.
    GPIO25 (Pin 22)  rot
    GPIO8  (Pin 24)  gelb
    GPIO7  (Pin 26)  grün
    GND    (Pin 20)  GND-Schiene
"""
# Der Docstring oben wird nicht ausgeführt. Er beschreibt Zweck und Verkabelung.

# sleep lässt das Programm eine Anzahl Sekunden warten.
from time import sleep

# PWMLED ist eine LED, die nicht nur an und aus kann, sondern auch Stufen dazwischen.
# Dafür schaltet gpiozero den Pin sehr schnell an und aus (PWM, 100 Mal pro Sekunde).
from gpiozero import PWMLED

# Helligkeit als Zahl von 0.0 (aus) bis 1.0 (voll). 0.6 heißt: 60 % der Zeit an.
ROT_HELLIGKEIT = 1.0     # rot leuchtet mit voller Kraft
GELB_HELLIGKEIT = 0.6    # gelb mit 60 %
GRUEN_HELLIGKEIT = 0.2   # grün mit 20 %

# So lange leuchtet jede Lampe allein, in Sekunden.
LEUCHTDAUER = 2

# So lange leuchten am Ende alle drei zusammen, in Sekunden.
VERGLEICH_DAUER = 3

# Legt die drei dimmbaren LEDs an. Die Zahl ist die GPIO-Nummer (BCM), nicht die Pinnummer.
rot = PWMLED(25)
gelb = PWMLED(8)
gruen = PWMLED(7)

# Eine Liste mit drei Einträgen, jeweils (LED, Helligkeit, Name für die Ausgabe).
# Die Reihenfolge bestimmt den Ablauf: erst rot, dann gelb, dann grün.
AMPEL = (
    (rot, ROT_HELLIGKEIT, "rot"),
    (gelb, GELB_HELLIGKEIT, "gelb"),
    (gruen, GRUEN_HELLIGKEIT, "grün"),
)

# Startmeldung im Terminal.
print("Ampel dimmen läuft. Beenden mit Strg+C.")

# Geschützter Block: Strg+C oder ein Fehler springen zu except bzw. finally.
try:
    # Endlosschleife, bis jemand Strg+C drückt.
    while True:
        # Geht die drei Einträge der Reihe nach durch.
        for led, helligkeit, name in AMPEL:
            # Zeigt an, welche Lampe gerade wie hell leuchtet, zum Beispiel "gelb: 60 %".
            # helligkeit * 100 macht aus 0.6 die Zahl 60, :.0f zeigt sie ohne Nachkommastelle.
            print(f"{name}: {helligkeit * 100:.0f} %")
            # Stellt die Helligkeit ein. Bei 0.6 ist der Pin in jedem Takt 60 % der Zeit an.
            led.value = helligkeit
            # Lampe so lange leuchten lassen.
            sleep(LEUCHTDAUER)
            # Lampe aus, bevor die nächste kommt.
            led.off()

        # Vergleich: alle drei gleichzeitig mit ihrer eigenen Helligkeit.
        print("Alle zusammen: rot 100 %, gelb 60 %, grün 20 %")
        # Die Unterstriche _ stehen für Werte, die wir hier nicht brauchen.
        for led, helligkeit, _ in AMPEL:
            led.value = helligkeit
        # Alle drei leuchten so lange zusammen.
        sleep(VERGLEICH_DAUER)
        # Alle drei wieder aus.
        for led, _, _ in AMPEL:
            led.off()
        # Eine Sekunde Dunkelheit, dann beginnt der Ablauf von vorn.
        sleep(1)
# Strg+C löst KeyboardInterrupt aus. Statt einer langen Fehlermeldung kommt eine kurze Zeile.
except KeyboardInterrupt:
    # \n ist ein Zeilenumbruch, damit die Meldung nicht hinter dem ^C klebt.
    print("\nBeendet.")
# finally läuft immer zum Schluss und räumt auf.
finally:
    for led, _, _ in AMPEL:
        # Lampe sicher aus.
        led.off()
        # GPIO-Pin wieder freigeben.
        led.close()
