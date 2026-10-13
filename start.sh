#!/bin/bash
# Startet die Dart-Club-Verwaltung und öffnet den Browser (Verwaltung + Monitor).
cd "$(dirname "$0")"
python3 server.py --port 8080 &
SRV=$!
sleep 1.5
xdg-open http://localhost:8080/ >/dev/null 2>&1 || true
echo "Monitor-Ansicht: http://localhost:8080/display  (im Browser auf den externen Monitor ziehen, F11 für Vollbild)"
wait $SRV
