"""SENTINEL Projektstart: Status-LED an GPIO25.

Die LED leuchtet 1 Sekunde und ist dann 2 Sekunden aus, bis Strg+C gedrückt wird.
Schaltung: GPIO25 (Pin 22) -> 330-Ohm-Widerstand -> LED (Anode) -> LED (Kathode) -> GND (Pin 30)
"""
from time import sleep

from gpiozero import LED

LED_PIN = 25      # BCM-Nummer, physisch Pin 22
AN_SEKUNDEN = 1
AUS_SEKUNDEN = 2

led = LED(LED_PIN)

print(f"SENTINEL: Status-LED an GPIO{LED_PIN} blinkt. Beenden mit Strg+C.")
try:
    while True:
        led.on()
        sleep(AN_SEKUNDEN)
        led.off()
        sleep(AUS_SEKUNDEN)
except KeyboardInterrupt:
    print("\nBeendet.")
finally:
    led.off()
    led.close()
