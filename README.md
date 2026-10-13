# Dart Club Pischelsdorf e.V. – Ranking-Verwaltung

Lokale Webseite für Gruppenphase + KO-Phase, Tabellen und Gesamt-Statistik.
Läuft komplett offline (nur Python 3, keine Installation von Paketen, kein Internet/WLAN nötig).

## Starten (Ubuntu-Laptop)
```bash
./start.sh
```
- Verwaltung (Laptop): http://localhost:8080/
- Monitor-Ansicht: http://localhost:8080/display → zweites Browserfenster auf den externen Monitor ziehen, `F11` = Vollbild. Aktualisiert sich alle 3 Sekunden selbst.

## Ablauf am Spieltag
1. **Turnier → Wer ist heute da?** Spieler anhaken (neue Spieler direkt anlegen).
2. Gruppenaufteilung wählen (Empfehlung ist vorausgewählt; ab 5 Spielern/Gruppe), Best-of, Single/Double Out, Startpunkte festlegen → **Auslosen**.
3. Auslosung prüfen (zwei Spieler anklicken = tauschen, „Neu auslosen“) → **Turnier starten**.
4. Ergebnisse per Klick eintragen (z. B. `2:1`). Falsch? „Ergebnis ändern“.
5. Nach der Gruppenphase: KO-Größe und Best-of je Runde (Standard BO3, Finale BO5) wählen → **KO-Phase starten**.

## Regeln
- Gruppe: jeder gegen jeden, Best-of frei wählbar (Standard BO3).
- Tabelle: 1. gewonnene Legs, 2. Leg-Differenz, 3. direkter Vergleich (bleibt es gleich, wird ein „=“ angezeigt → Stechen).
- KO: Setzung nach Gruppenplatz (bei 2 Gruppen: A1–B4, B2–A3, B1–A4, A2–B3). Bei 3+ Gruppen werden fehlende Plätze mit den besten Nächstplatzierten (Wildcards) aufgefüllt, Gruppengleiche treffen möglichst nicht in Runde 1 aufeinander.

## Daten
- Datenbank: `data/dart.db` (SQLite). Backups automatisch bei Turnierende in `data/backups/`, manuell unter Spieler → „Backup herunterladen“.
- Tests: `python3 -m unittest discover -s tests`
