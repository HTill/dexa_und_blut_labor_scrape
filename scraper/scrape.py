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

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def search_overpass(query: str) -> list[dict]:
    """Führt eine Overpass-Query aus und gibt Elemente zurück."""
    resp = requests.get(OVERPASS_URL, params={"data": query}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("elements", [])


if __name__ == "__main__":
    query = """
    [out:json];
    area["ISO3166-1"="DE"];
    node["amenity"="doctors"]["healthcare:speciality"~"radiology"](area);
    out center;
    """
    results = search_overpass(query.strip())
    print(f"Overpass Rohdaten: {len(results)} Einträge")
    print("Manuelle Nachprüfung nötig — Overpass unterscheidet nicht Body Composition vs. Knochendichte.")
