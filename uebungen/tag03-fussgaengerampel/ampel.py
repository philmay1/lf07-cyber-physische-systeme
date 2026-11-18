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
# Der Docstring oben wird nicht ausgeführt. Er beschreibt Zweck und Verkabelung.

# threading bringt Werkzeuge für Programmteile, die gleichzeitig laufen.
# Wir brauchen daraus das Event, eine Art Merkzettel zwischen Taster und Hauptschleife.
import threading

# datetime liefert die aktuelle Uhrzeit. Wir nutzen sie als Zeitstempel im Log.
from datetime import datetime

# sleep lässt das Programm eine Anzahl Sekunden warten. So lange bleibt eine Ampelphase stehen.
from time import sleep

# Aus gpiozero holen wir drei fertige Bauteil-Klassen:
# LED für die Lampen, Button für den Taster, Buzzer für den Summer.
from gpiozero import LED, Button, Buzzer

# ---------- Zeiten in Sekunden (für den Unterricht verkürzt) ----------
# Alle Zeiten stehen als Konstanten oben. Wer die Ampel langsamer haben will,
# ändert nur hier eine Zahl und muss nicht im Code suchen.
GRUEN_MINDESTENS = 5     # so lange bleibt die Autoampel mindestens grün
GELB = 3                 # gelb vor rot (innerorts 3 s)
RAEUMEN_AUTOS = 2        # alle rot, damit die Kreuzung leer ist
FUSS_GRUEN = 6           # Fußgänger dürfen gehen
RAEUMEN_FUSS = 3         # alle rot, letzte Fußgänger kommen rüber
ROT_GELB = 1             # rot und gelb zusammen, gleich wird grün
# Schalter für das Orientierungsticken. False heißt aus, True heißt an.
ORIENTIERUNGSTON = False # leises Ticken im Wartezustand, wie an echten Ampeln

# Legt die drei Autolampen an: rot an GPIO25, gelb an GPIO8, grün an GPIO7.
# Mehrere Variablen auf einmal zuweisen spart drei einzelne Zeilen.
auto_rot, auto_gelb, auto_gruen = LED(25), LED(8), LED(7)

# Legt die beiden Fußgängerlampen an: rot an GPIO23, grün an GPIO24.
fuss_rot, fuss_gruen = LED(23), LED(24)

# Summer an GPIO18. active_high=False dreht die Logik um: summer.on() legt den
# Pin auf LOW (0 V), denn erst dann schaltet der PNP-Transistor durch und der Summer piept.
summer = Buzzer(18, active_high=False)

# Taster an GPIO12. pull_up=True schaltet den internen Pull-up-Widerstand ein:
# Ohne Druck liegt der Pin auf HIGH, beim Drücken zieht der Taster ihn auf GND (LOW).
# bounce_time=0.05 ignoriert für 50 ms weitere Signale, weil Tasterkontakte beim
# Drücken kurz prellen und sonst mehrere Klicks gemeldet würden.
taster = Button(12, pull_up=True, bounce_time=0.05)

# Das Event ist ein Merker mit zwei Zuständen: gesetzt oder nicht gesetzt.
# Der Taster setzt ihn, die Hauptschleife wartet darauf. Das funktioniert auch
# zwischen zwei Threads, denn gpiozero ruft die Taster-Funktion in einem eigenen Thread auf.
anforderung = threading.Event()


# Gibt eine Meldung mit Uhrzeit aus, zum Beispiel "09:15:03  Autos: gelb".
def log(text):
    # {datetime.now():%H:%M:%S} formatiert die Uhrzeit als Stunden:Minuten:Sekunden.
    # flush=True schreibt sofort ins Terminal, statt die Ausgabe zu puffern. Das ist
    # wichtig, wenn das Programm über SSH läuft und man jede Phase live sehen will.
    print(f"{datetime.now():%H:%M:%S}  {text}", flush=True)


# Die Parameter haben Standardwerte: Autolampen aus, Fußgänger rot an, Fußgänger grün aus.
# Beim Aufruf nennt man nur, was davon abweicht, zum Beispiel lampen(gelb=True).
def lampen(rot=False, gelb=False, gruen=False, f_rot=True, f_gruen=False):
    """Setzt alle fünf Lampen auf einmal, damit kein Zwischenzustand entsteht."""
    # Die Schleife geht fünf Paare durch, jeweils (Lampe, gewünschter Zustand).
    for led, an in ((auto_rot, rot), (auto_gelb, gelb), (auto_gruen, gruen),
                    (fuss_rot, f_rot), (fuss_gruen, f_gruen)):
        # value = True schaltet die Lampe an, value = False schaltet sie aus.
        led.value = an


# Diese Funktion läuft automatisch, sobald jemand den Taster drückt.
def gedrueckt():
    # is_lit prüft, ob die Fußgänger-Grün-Lampe gerade leuchtet.
    if fuss_gruen.is_lit:
        # Dann ist nichts zu tun, die Funktion endet hier sofort.
        return                          # Fußgänger haben schon grün
    # Nur reagieren, wenn noch keine Anforderung gespeichert ist.
    # So piept es bei fünfmal Drücken nicht fünfmal.
    if not anforderung.is_set():
        # Setzt den Merker. Die Hauptschleife sieht jetzt: jemand wartet.
        anforderung.set()
        # Meldung im Terminal, dass der Druck angekommen ist.
        log("Taster gedrückt: Anforderung gespeichert, Signal kommt")
        # Zwei kurze Pieptöne (je 0,08 s) als Bestätigung. background=True lässt
        # den Summer nebenher piepen, die Funktion wartet nicht darauf.
        summer.beep(on_time=0.08, off_time=0.08, n=2, background=True)   # Quittung


# Wird einmal beim Programmstart aufgerufen.
def einschalten():
    """Einschaltprogramm wie bei echten Anlagen: erst gelb blinken, dann rot."""
    # Startmeldung ins Terminal.
    log("Start: Autoampel blinkt gelb")
    # Alle Lampen aus. f_rot=False überschreibt den Standard, sonst wäre Fußgänger rot an.
    lampen(f_rot=False)
    # Gelb blinkt dreimal (0,5 s an, 0,5 s aus). background=False heißt: Das Programm
    # wartet hier, bis alle drei Blinker fertig sind, also etwa 3 Sekunden.
    auto_gelb.blink(on_time=0.5, off_time=0.5, n=3, background=False)
    # Autos rot. Fußgänger rot ist über den Standardwert ebenfalls an, also alle rot.
    lampen(rot=True)
    # Kurze Pause mit allen auf rot, bevor der normale Betrieb startet.
    sleep(RAEUMEN_AUTOS)


# Ein kompletter Durchlauf für die Fußgänger, von Autos gelb bis Autos rot-gelb.
def zyklus_fussgaenger():
    # Phase 1: Autos bekommen gelb, damit sie abbremsen können.
    log("Autos: gelb")
    lampen(gelb=True)
    sleep(GELB)

    # Phase 2: Alle rot. Autos, die noch auf der Kreuzung sind, fahren raus.
    log("Alle rot (Räumzeit Autos)")
    lampen(rot=True)
    sleep(RAEUMEN_AUTOS)

    # Phase 3: Fußgänger grün, Autos bleiben rot.
    log("Fußgänger: grün, Freigabe-Takt")
    lampen(rot=True, f_rot=False, f_gruen=True)
    # Merker zurücksetzen. Die Anforderung ist erledigt, der nächste Druck zählt neu.
    anforderung.clear()                 # Anforderung ist erfüllt
    # Schnelles Ticken für blinde Menschen: 0,05 s Ton, 0,2 s Pause. Ohne n läuft
    # das endlos im Hintergrund, bis summer.off() kommt.
    summer.beep(on_time=0.05, off_time=0.2, background=True)
    # So lange dürfen die Fußgänger gehen.
    sleep(FUSS_GRUEN)
    # Ticken aus, die Grünphase ist vorbei.
    summer.off()

    # Phase 4: Alle rot. Wer noch auf der Straße ist, kommt sicher rüber.
    log("Alle rot (Räumzeit Fußgänger)")
    lampen(rot=True)
    sleep(RAEUMEN_FUSS)

    # Phase 5: Autos rot und gelb gleichzeitig, das kündigt grün an (deutsche Phasenfolge).
    log("Autos: rot und gelb")
    lampen(rot=True, gelb=True)
    sleep(ROT_GELB)


# Hauptprogramm mit der Endlosschleife.
def main():
    # Verbindet den Taster mit der Funktion gedrueckt. Ohne Klammern, denn wir
    # übergeben die Funktion selbst. gpiozero ruft sie später bei jedem Druck auf.
    taster.when_pressed = gedrueckt
    # Einschaltprogramm einmal ablaufen lassen.
    einschalten()
    # Ab hier läuft die Ampel endlos, bis Strg+C kommt.
    while True:
        # Grundzustand: Autos grün, Fußgänger rot.
        log("Autos: grün, Fußgänger: rot, warte auf Taster")
        lampen(gruen=True)
        # Nur wenn der Schalter oben auf True steht: langsames Ticken (alle 1,2 s),
        # damit blinde Menschen den Taster am Mast finden.
        if ORIENTIERUNGSTON:
            summer.beep(on_time=0.02, off_time=1.2, background=True)
        # Autos bekommen ihre Mindestgrünzeit, auch wenn schon jemand gedrückt hat.
        sleep(GRUEN_MINDESTENS)        # Autos fahren in jedem Fall ihre Mindestzeit
        # Wartet, bis der Merker gesetzt ist. War schon gedrückt, geht es sofort weiter.
        anforderung.wait()             # danach erst, wenn jemand gedrückt hat
        # Orientierungsticken aus, bevor der Fußgängerzyklus startet.
        summer.off()
        # Fußgängerphase komplett durchlaufen, danach beginnt die Schleife von vorn.
        zyklus_fussgaenger()


# Dieser Block läuft nur, wenn man die Datei direkt startet (python3 ampel.py),
# nicht wenn ein anderes Programm sie mit import einbindet.
if __name__ == "__main__":
    # Geschützter Block: Abbruch oder Fehler springen zu except bzw. finally.
    try:
        # Startet die Ampel.
        main()
    # Strg+C löst KeyboardInterrupt aus. Statt Fehlermeldung kommt eine kurze Zeile.
    except KeyboardInterrupt:
        log("Beendet mit Strg+C")
    # finally läuft immer zum Schluss und räumt auf.
    finally:
        # Summer sicher aus.
        summer.off()
        # Alle Lampen aus, auch Fußgänger rot (f_rot=False).
        lampen(f_rot=False)
        # Gibt jedes Bauteil und damit seinen GPIO-Pin wieder frei.
        for teil in (auto_rot, auto_gelb, auto_gruen, fuss_rot, fuss_gruen, summer, taster):
            teil.close()
