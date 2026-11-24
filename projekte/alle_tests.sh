#!/bin/bash
# Führt alle automatischen Tests der SENTINEL-Projekte nacheinander aus (auf dem Pi).
# Aufruf aus dem Repo:  bash projekte/alle_tests.sh
cd "$(dirname "$0")" || exit 1                 # in den Ordner projekte wechseln
fehler=0                                       # Anzahl fehlgeschlagener Testdateien
for test in gemeinsam/test_pinplan.py 0*/test_*.py; do   # alle Testdateien in fester Reihenfolge
    echo "== $test"                             # Überschrift je Testdatei
    ( cd "$(dirname "$test")" && python3 "$(basename "$test")" ) 2>&1 | grep -E "^(OK|FEHLER|HINWEIS)|Tests"   # nur Ergebniszeilen zeigen
    [ "${PIPESTATUS[0]}" -eq 0 ] || fehler=$((fehler + 1))   # Exit-Code des Tests auswerten
done
echo; [ "$fehler" -eq 0 ] && echo "Alle Testdateien bestanden." || echo "$fehler Testdatei(en) mit Fehlern."   # Gesamtergebnis
exit "$fehler"                                 # Exit-Code für Skripte
