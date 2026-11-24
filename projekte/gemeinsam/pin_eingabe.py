"""PIN-Eingabe als Zustandsautomat (Tag 5, AB3, Abschnitt 6.6).

Regeln: höchstens 4 Ziffern, * löscht die letzte Ziffer, # prüft nur bei genau 4 Stellen,
nach 10 s ohne Taste wird alles gelöscht. Der Puffer wird nie ausgegeben oder geloggt.
"""
PIN_LAENGE = 4                                 # vierstellige PIN laut Arbeitsblatt
TIMEOUT_S = 10.0                               # input_timeout_seconds aus der config


class PinEingabe:                              # merkt sich die getippten Ziffern und entscheidet, was passiert
    def __init__(self, timeout_s=TIMEOUT_S):   # Timeout ist einstellbar (für Tests kürzer)
        self.puffer = []                       # die getippten Ziffern, nur im Speicher
        self.timeout_s = timeout_s             # Timeout merken
        self.letzte_taste = None               # Zeitpunkt der letzten Taste (None = leer)

    def taste(self, zeichen, jetzt):           # verarbeitet eine Taste; gibt ein Ergebnis-Wort zurück
        self.timeout_pruefen(jetzt)            # zuerst schauen, ob die alte Eingabe verfallen ist
        if zeichen.isdigit():                  # Ziffer 0-9
            if len(self.puffer) >= PIN_LAENGE: # schon 4 Ziffern
                return "voll"                  # fünfte Ziffer wird ignoriert (ZT-04)
            self.puffer.append(zeichen)        # Ziffer anhängen
            self.letzte_taste = jetzt          # Timeout neu starten
            return "ziffer"                    # Rückmeldung für die gelbe LED
        if zeichen == "*":                     # Löschen
            if self.puffer:                    # nur wenn etwas da ist ...
                self.puffer.pop()              # ... letzte Ziffer entfernen
            self.letzte_taste = jetzt if self.puffer else None  # leer = kein Timeout mehr nötig
            return "geloescht"                 # Rückmeldung
        if zeichen == "#":                     # Bestätigen
            if len(self.puffer) != PIN_LAENGE: # nicht genau 4 Stellen (ZT-03)
                return "unvollstaendig"        # keine Prüfung, Puffer bleibt zum Weitertippen
            pin = "".join(self.puffer)         # die vier Ziffern zu einem Text
            self.leeren()                      # Puffer sofort löschen, die PIN bleibt nicht im Speicher liegen
            return ("pruefen", pin)            # der Aufrufer prüft die PIN und vergisst sie danach
        return "ignoriert"                     # A, B, C, D haben keine Funktion

    def timeout_pruefen(self, jetzt):          # löscht eine angefangene Eingabe nach 10 s
        if self.letzte_taste is not None and jetzt - self.letzte_taste > self.timeout_s:  # Zeit abgelaufen?
            self.leeren()                      # Puffer vollständig löschen (ZT-05)
            return True                        # ja, Timeout ist passiert
        return False                           # nein

    def leeren(self):                          # Puffer sicher leeren
        self.puffer.clear()                    # alle Ziffern entfernen
        self.letzte_taste = None               # kein laufender Timeout

    @property                                  # wie eine Variable lesbar: eingabe.stellen
    def stellen(self):                         # wie viele Ziffern sind getippt (für die Anzeige, nie die Ziffern selbst)
        return len(self.puffer)                # nur die Anzahl
