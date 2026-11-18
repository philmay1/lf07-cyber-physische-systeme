"""Fußgängerampel mit Anforderungstaster und Blindensignal (LF07 Tag 3).

Verbesserte Fassung der Ampel aus dem Raspberry-Pi-Handbuch (S. 142):
Python statt Scratch, deutsche Phasenfolge, eigene Fußgängerampel, Räumzeiten,
Quittungston beim Drücken und ein Freigabe-Takt für blinde Menschen.

Schaltung (Pi 400, alle Signale in der unteren Reihe der Stiftleiste):
    GPIO25 (Pin 22)  Auto rot          über 220 Ohm
    GPIO8  (Pin 24)  Auto gelb         über 220 Ohm
    GPIO7  (Pin 26)  Auto grün         über 220 Ohm
    GPIO23 (Pin 16)  Fußgänger rot     über 220 Ohm
    GPIO24 (Pin 18)  Fußgänger grün    über 220 Ohm
    GPIO12 (Pin 32)  Taster gegen GND  (interner Pull-up)
    GPIO18 (Pin 12)  Summer über PNP-Transistor, 1 kOhm an der Basis
    GND    (Pin 20)  GND-Schiene, 3V3 (Pin 17, obere Reihe) an den Emitter

Der PNP-Transistor schaltet bei LOW durch. Deshalb steht beim Summer active_high=False.
Beenden mit Strg+C, danach sind alle Lampen und der Summer aus.
"""
import threading
from datetime import datetime
from time import sleep

from gpiozero import LED, Button, Buzzer

# ---------- Zeiten in Sekunden (für den Unterricht verkürzt) ----------
GRUEN_MINDESTENS = 5     # so lange bleibt die Autoampel mindestens grün
GELB = 3                 # gelb vor rot (innerorts 3 s)
RAEUMEN_AUTOS = 2        # alle rot, damit die Kreuzung leer ist
FUSS_GRUEN = 6           # Fußgänger dürfen gehen
RAEUMEN_FUSS = 3         # alle rot, letzte Fußgänger kommen rüber
ROT_GELB = 1             # rot und gelb zusammen, gleich wird grün
ORIENTIERUNGSTON = False # leises Ticken im Wartezustand, wie an echten Ampeln

auto_rot, auto_gelb, auto_gruen = LED(25), LED(8), LED(7)
fuss_rot, fuss_gruen = LED(23), LED(24)
summer = Buzzer(18, active_high=False)
taster = Button(12, pull_up=True, bounce_time=0.05)

anforderung = threading.Event()


def log(text):
    print(f"{datetime.now():%H:%M:%S}  {text}", flush=True)


def lampen(rot=False, gelb=False, gruen=False, f_rot=True, f_gruen=False):
    """Setzt alle fünf Lampen auf einmal, damit kein Zwischenzustand entsteht."""
    for led, an in ((auto_rot, rot), (auto_gelb, gelb), (auto_gruen, gruen),
                    (fuss_rot, f_rot), (fuss_gruen, f_gruen)):
        led.value = an


def gedrueckt():
    if fuss_gruen.is_lit:
        return                          # Fußgänger haben schon grün
    if not anforderung.is_set():
        anforderung.set()
        log("Taster gedrückt: Anforderung gespeichert, Signal kommt")
        summer.beep(on_time=0.08, off_time=0.08, n=2, background=True)   # Quittung


def einschalten():
    """Einschaltprogramm wie bei echten Anlagen: erst gelb blinken, dann rot."""
    log("Start: Autoampel blinkt gelb")
    lampen(f_rot=False)
    auto_gelb.blink(on_time=0.5, off_time=0.5, n=3, background=False)
    lampen(rot=True)
    sleep(RAEUMEN_AUTOS)


def zyklus_fussgaenger():
    log("Autos: gelb")
    lampen(gelb=True)
    sleep(GELB)

    log("Alle rot (Räumzeit Autos)")
    lampen(rot=True)
    sleep(RAEUMEN_AUTOS)

    log("Fußgänger: grün, Freigabe-Takt")
    lampen(rot=True, f_rot=False, f_gruen=True)
    anforderung.clear()                 # Anforderung ist erfüllt
    summer.beep(on_time=0.05, off_time=0.2, background=True)
    sleep(FUSS_GRUEN)
    summer.off()

    log("Alle rot (Räumzeit Fußgänger)")
    lampen(rot=True)
    sleep(RAEUMEN_FUSS)

    log("Autos: rot und gelb")
    lampen(rot=True, gelb=True)
    sleep(ROT_GELB)


def main():
    taster.when_pressed = gedrueckt
    einschalten()
    while True:
        log("Autos: grün, Fußgänger: rot, warte auf Taster")
        lampen(gruen=True)
        if ORIENTIERUNGSTON:
            summer.beep(on_time=0.02, off_time=1.2, background=True)
        sleep(GRUEN_MINDESTENS)        # Autos fahren in jedem Fall ihre Mindestzeit
        anforderung.wait()             # danach erst, wenn jemand gedrückt hat
        summer.off()
        zyklus_fussgaenger()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Beendet mit Strg+C")
    finally:
        summer.off()
        lampen(f_rot=False)
        for teil in (auto_rot, auto_gelb, auto_gruen, fuss_rot, fuss_gruen, summer, taster):
            teil.close()
