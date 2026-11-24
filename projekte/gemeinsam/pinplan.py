"""Zentraler Pinplan für alle SENTINEL-Projekte ab Projekt 02.

Grundlage ist das Anschlussbild des Dozenten (Pi 400 + Keypad + SG90).
Alle Zahlen sind BCM-Nummern (GPIO-Namen), in den Kommentaren steht der physische Pin.
Ein Pin wird nur hier geändert, alle Projekte lesen ihn von hier.
"""

# ---------- Ampel-LEDs (aus Tag 3, bleiben gesteckt) ----------
LED_ROT = 25        # Pin 22: rot = falsch, gesperrt, Alarm
LED_GELB = 8        # Pin 24: gelb = Tastendruck, Countdown, Senden
LED_GRUEN = 7       # Pin 26: grün = Tür offen, Status in Ordnung

# ---------- Eingänge ----------
TASTER = 27         # Pin 13: Taster gegen GND, interner Pull-up (vorher GPIO12, der ist jetzt Keypad C1)
BEWEGUNGSMELDER = 17  # Pin 11: optionaler PIR-Ausgang für Projekt 04 (nur 3,3 V am Ausgang!)

# ---------- Summer über PNP-Transistor ----------
SUMMER = 22         # Pin 15: vorher GPIO18, der ist jetzt das Servo-Signal

# ---------- 4x4-Keypad laut Bild des Dozenten ----------
KEYPAD_ZEILEN = (5, 6, 13, 19)     # Pin 29, 31, 33, 35: R1 bis R4
KEYPAD_SPALTEN = (12, 16, 20, 21)  # Pin 32, 36, 38, 40: C1 bis C4
KEYPAD_TASTEN = (                  # Tastenbelegung Zeile für Zeile, wie auf dem Keypad aufgedruckt
    ("1", "2", "3", "A"),  # Zeile 1
    ("4", "5", "6", "B"),  # Zeile 2
    ("7", "8", "9", "C"),  # Zeile 3
    ("*", "0", "#", "D"),  # Zeile 4
)

# ---------- Servo SG90 ----------
SERVO = 18          # Pin 12: Signal (orange/gelb). +5 V an Pin 2 (rot), GND an Pin 6 (braun/schwarz)

# Alle belegten Pins auf einen Blick. Der Test prüft damit, dass kein Pin doppelt vergeben ist.
ALLE = {                                                                     # Wörterbuch: Name -> GPIO-Nummer
    "LED_ROT": LED_ROT, "LED_GELB": LED_GELB, "LED_GRUEN": LED_GRUEN,         # die drei Ampel-LEDs
    "TASTER": TASTER, "BEWEGUNGSMELDER": BEWEGUNGSMELDER,                     # die Eingänge
    "SUMMER": SUMMER, "SERVO": SERVO,                                         # Summer und Servo
    **{f"KEYPAD_R{i + 1}": p for i, p in enumerate(KEYPAD_ZEILEN)},          # R1..R4 automatisch durchnummeriert
    **{f"KEYPAD_C{i + 1}": p for i, p in enumerate(KEYPAD_SPALTEN)},         # C1..C4 automatisch durchnummeriert
}                                                                            # Ende des Wörterbuchs
