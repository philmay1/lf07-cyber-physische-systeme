"""Tür mit Servo SG90, LED-Rückmeldung und Summer (Tag 5, AB2 und AB3).

Sichere Sequenz laut Arbeitsblatt: Start verriegelt (0°), bei richtiger PIN kontrolliert
auf 90°, 3 s offen halten, zurück auf 0°, danach PWM aus. Bei falscher PIN bewegt sich nichts.
Im Cleanup wird zuerst verriegelt, dann alles abgeschaltet.

Servo: Signal GPIO18 (Pin 12), +5 V Pin 2, GND Pin 6. Laut Bild des Dozenten nur für kurze
Tests ohne Last aus dem Pi versorgen. Bei Ruckeln oder Neustart des Pi: externes 5-V-Netzteil
mit gemeinsamer Masse nehmen.
"""
import time                                    # Wartezeiten der Sequenz

from gpiozero import LED, AngularServo, Buzzer  # Servo mit Winkelangabe, LEDs, Summer

import pinplan                                 # zentrale Pinbelegung

VERRIEGELT = 0                                 # Winkel in Grad: Tür zu
OFFEN = 90                                     # Winkel in Grad: Tür auf
OFFEN_HALTEN_S = 3                             # so lange bleibt die Tür offen
FAHRZEIT_S = 0.6                               # Zeit, die der SG90 für 90° braucht (etwa 0,1 s pro 60°, mit Reserve)


def servo_fabrik():                            # wählt die Pin-Fabrik für ein ruhiges Servo-Signal
    try:                                       # pigpio erzeugt die Pulse hardwaregenau, der Servo zittert nicht
        from gpiozero.pins.pigpio import PiGPIOFactory  # nur verfügbar, wenn pigpio installiert ist
        fabrik = PiGPIOFactory()               # verbindet sich mit dem Dienst pigpiod
        fabrik.pin(pinplan.SERVO)              # Test, ob der Dienst wirklich läuft (wirft sonst)
        return fabrik                          # pigpio verwenden
    except Exception:                          # Dienst läuft nicht oder Bibliothek fehlt (auch im Test mit Mock-Pins)
        return None                            # Standard-Fabrik von gpiozero (Software-PWM, kann leicht zittern)


class Tuer:                                    # Servo + Rückmeldung als eine Einheit
    def __init__(self, fabrik="auto"):         # fabrik="auto": pigpio wenn möglich
        fabrik = servo_fabrik() if fabrik == "auto" else fabrik  # Fabrik bestimmen
        self.servo = AngularServo(             # Servo mit Winkeln statt Pulsbreiten ansprechen
            pinplan.SERVO,                     # GPIO18
            initial_angle=VERRIEGELT,          # sofort in die sichere Startposition (SV-01, SV-06)
            min_angle=VERRIEGELT, max_angle=OFFEN,  # nur der geprüfte Bereich 0° bis 90°
            min_pulse_width=1.0 / 1000,        # 1,0 ms = 0° (Startwert laut AB2, am echten Servo prüfen)
            max_pulse_width=2.0 / 1000,        # 2,0 ms = 90°
            pin_factory=fabrik,                # None = Standardfabrik
        )
        self.gruen = LED(pinplan.LED_GRUEN)    # grün = Tür offen
        self.rot = LED(pinplan.LED_ROT)        # rot = falsch oder Fehler
        self.gelb = LED(pinplan.LED_GELB)      # gelb = Tastendruck erkannt
        self.summer = Buzzer(pinplan.SUMMER, active_high=False)  # PNP-Transistor schaltet bei LOW
        time.sleep(FAHRZEIT_S)                 # Servo in Startposition fahren lassen
        self.servo.detach()                    # danach kein Signal mehr: Servo hält ohne Last, zittert nicht

    def taste_quittieren(self):                # kurze Rückmeldung für jede Taste
        self.gelb.blink(0.08, 0, n=1, background=True)  # gelb blitzt 80 ms

    def oeffnen(self):                         # Sequenz bei richtiger PIN (ZT-01)
        self.rot.off()                         # eventuelle Fehleranzeige aus
        self.gruen.on()                        # grün während der ganzen Offen-Phase
        self.summer.beep(0.08, 0.08, n=2, background=True)  # zwei kurze Pieptöne
        self.servo.angle = OFFEN               # kontrolliert auf 90°
        time.sleep(FAHRZEIT_S + OFFEN_HALTEN_S)  # hinfahren und 3 s offen halten; Eingaben werden so lange nicht gelesen
        self.verriegeln()                      # zurück in die sichere Position
        self.gruen.off()                       # grün aus erst nach dem Verriegeln

    def verriegeln(self):                      # zurück auf 0° und PWM aus
        self.servo.angle = VERRIEGELT          # Sollwert verriegelt
        time.sleep(FAHRZEIT_S)                 # Zeit zum Hinfahren
        self.servo.detach()                    # PWM beenden (AB2, Schritt 5)

    def falsch(self):                          # Rückmeldung bei falscher PIN (ZT-02): keine Bewegung
        self.summer.beep(0.4, 0, n=1, background=True)  # ein langer Ton
        self.rot.blink(1, 0, n=1, background=True)  # rot 1 s

    def hinweis(self):                         # Timeout oder unvollständige Eingabe
        self.rot.blink(0.2, 0.2, n=2, background=True)  # zweimal 200 ms blinken (AB2, LED-Feedback)

    def fehler(self):                          # technischer Fehler (z. B. Datenbank weg): bleibt verriegelt
        self.rot.blink(1, 1, n=3, background=True)  # langsames Blinken

    def schliessen(self):                      # Cleanup laut AB2, Schritt 6
        try:                                   # auch wenn der Servo zickt, sollen LEDs und Pins frei werden
            self.verriegeln()                  # zuerst sichere Position anfahren
        finally:                               # danach in jedem Fall
            for geraet in (self.gruen, self.rot, self.gelb, self.summer, self.servo):  # alle Geräte
                geraet.close()                 # Pin freigeben, LEDs und Summer gehen dabei aus
