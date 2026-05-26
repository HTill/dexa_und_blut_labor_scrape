"""
Scraping-Skript zur Erfassung von DEXA-Scan-Anbietern und Blutlaboren im DACH-Raum.

Aktuell: Manuelle/API-gestützte Erfassung mit OpenStreetMap Overpass API als Startpunkt.
Ziel: Daten nach schema.json sammeln und in providers.json ablegen.
"""

import json
import time
from pathlib import Path

import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "providers.json"

# Overpass API — DEXA/Body Composition in DACH
OVERPASS_QUERY_DEXA = """
[out:json];
area["ISO3166-1"="DE"]->.de;
area["ISO3166-1"="AT"]->.at;
area["ISO3166-1"="CH"]->.ch;
(
  node["amenity"="clinic"]["description"~"dex
body composition", i](area.de);
  node["amenity"="clinic"]["description"~"dex
body composition", i](area.at);
  node["amenity"="clinic"]["description"~"dex
body composition", i](area.ch);
);
out center;
"""

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def search_overpass(query: str) -> list[dict]:
    """Führt eine Overpass-Query aus und gibt Elemente zurück."""
    resp = requests.get(OVERPASS_URL, params={"data": query}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("elements", [])


# TODO: Erste Recherche — über Overpass findet man primär Krankenhäuser/Radiologien.
# Besser: Gezielte Google-Suche nach "DEXA Body Composition Selbstzahler [Stadt]"
# + manuelle Verifikation.


if __name__ == "__main__":
    print("Starte Overpass-Recherche für DEXA-Anbieter ...")
    results = search_overpass(OVERPASS_QUERY_DEXA.strip())
    print(f"Gefunden: {len(results)} Einträge (roh, ungefiltert)")
    print("Hinweis: Overpass liefert keine Unterscheidung Body Composition/Knochendichte.")
    print("Manuelle Nachprüfung nötig.")
