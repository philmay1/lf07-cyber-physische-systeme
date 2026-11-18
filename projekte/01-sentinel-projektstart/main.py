"""SENTINEL Projektstart: Status-LED an GPIO25.

Die LED leuchtet 1 Sekunde und ist dann 2 Sekunden aus, bis Strg+C gedrückt wird.
Schaltung: GPIO25 (Pin 22) -> 220-Ohm-Widerstand -> LED (Anode) -> LED (Kathode) -> GND (Pin 30)
"""
# Der Text in den drei Anführungszeichen oben ist der Docstring. Python führt ihn
# nicht aus. Er beschreibt nur, was das Programm macht und wie die Schaltung aussieht.

# Aus dem Modul "time" holen wir nur die Funktion sleep. Sie lässt das Programm
# eine bestimmte Zahl Sekunden warten, zum Beispiel wartet sleep(1) genau 1 Sekunde.
from time import sleep

# Aus der Bibliothek gpiozero holen wir die Klasse LED. Sie übernimmt die ganze
# Pin-Steuerung, wir müssen nur noch "an" oder "aus" sagen.
from gpiozero import LED

# Konstante für den Pin. 25 ist die BCM-Nummer (so heißt der Pin im Chip).
# Auf der Stiftleiste ist das der physische Pin 22. gpiozero erwartet die BCM-Nummer.
LED_PIN = 25      # BCM-Nummer, physisch Pin 22

# Wie lange die LED pro Durchlauf leuchtet, in Sekunden.
AN_SEKUNDEN = 1

# Wie lange die LED pro Durchlauf aus bleibt, in Sekunden.
AUS_SEKUNDEN = 2

# Erzeugt ein LED-Objekt für GPIO25. Ab jetzt steuert die Variable "led" genau
# diesen Pin. Der Pin wird dabei als Ausgang eingestellt und ist zuerst aus.
led = LED(LED_PIN)

# Gibt eine Startmeldung im Terminal aus. Das f vor dem Text macht einen f-String:
# {LED_PIN} wird durch den Wert 25 ersetzt, im Terminal steht also "GPIO25".
print(f"SENTINEL: Status-LED an GPIO{LED_PIN} blinkt. Beenden mit Strg+C.")

# try leitet einen geschützten Block ein. Kommt es darin zu einem Abbruch oder
# Fehler, springt Python zu except bzw. finally, statt einfach abzustürzen.
try:
    # Endlosschleife: True ist immer wahr, also läuft die Schleife, bis jemand
    # das Programm mit Strg+C abbricht.
    while True:
        # Schaltet GPIO25 auf 3,3 V. Strom fließt durch Widerstand und LED, sie leuchtet.
        led.on()
        # Wartet 1 Sekunde (Wert aus AN_SEKUNDEN). So lange bleibt die LED an.
        sleep(AN_SEKUNDEN)
        # Schaltet GPIO25 auf 0 V. Es fließt kein Strom mehr, die LED geht aus.
        led.off()
        # Wartet 2 Sekunden (Wert aus AUS_SEKUNDEN). Danach beginnt die Schleife von vorn.
        sleep(AUS_SEKUNDEN)
# Strg+C löst in Python eine KeyboardInterrupt-Ausnahme aus. Hier fangen wir sie ab,
# damit statt einer langen Fehlermeldung nur ein kurzer Hinweis erscheint.
except KeyboardInterrupt:
    # \n ist ein Zeilenumbruch, damit "Beendet." nicht hinter dem ^C im Terminal klebt.
    print("\nBeendet.")
# finally läuft immer zum Schluss, egal ob das Programm normal endet, abgebrochen
# wird oder an einem anderen Fehler scheitert. Hier wird aufgeräumt.
finally:
    # Schaltet die LED sicher aus, falls sie beim Abbruch gerade an war.
    led.off()
    # Gibt GPIO25 wieder frei, damit andere Programme den Pin nutzen können.
    led.close()
