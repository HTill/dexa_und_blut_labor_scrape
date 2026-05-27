"""
Geocode-Tool — füllt fehlende Koordinaten (0.0, 0.0) via Nominatim.

Usage:
    python -m scraper.tools.geocode
    python -m scraper.tools.geocode --file amedes
    python -m scraper.tools.geocode --dry-run

Geht alle unchecked/*.json Dateien durch und geocodiert Einträge
mit Koordinaten (0.0, 0.0) über die Nominatim API (OpenStreetMap).
Nutzt RequestKit für direktes Nominatim-Geocoding.
"""

import json
import sys
from pathlib import Path

from scraper.tools.request_kit import RequestKit

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
UNCHECKED_DIR = DATA_DIR / "unchecked"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
RATE_LIMIT = 1.2  # Nominatim Rate-Limit

rk = RequestKit(rate=RATE_LIMIT, retries=3)


def geocode_address(street: str, postal_code: str, city: str, country: str = "DE") -> tuple[float, float]:
    parts = [street, postal_code, city]
    address_str = ", ".join(p for p in parts if p)
    if not address_str:
        return 0.0, 0.0

    country_map = {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"}
    country_name = country_map.get(country, country)
    address_str += f", {country_name}"

    try:
        resp = rk.get(
            NOMINATIM_URL,
            params={"q": address_str, "format": "json", "limit": 1, "countrycodes": country.lower()},
            headers={"User-Agent": "DeXaBlutLaborScraper/1.0"},
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return 0.0, 0.0


def needs_geocoding(entry: dict) -> bool:
    """Prüft ob ein Eintrag Geocoding braucht (Koordinaten 0,0)."""
    coords = entry.get("coordinates", {})
    lat = coords.get("lat", 0)
    lng = coords.get("lng", 0)
    return lat == 0.0 and lng == 0.0


def geocode_file(filepath: Path, dry_run: bool = False) -> int:
    """Geocodiert alle 0,0-Einträge in einer Datei. Gibt Anzahl geocodierter Einträge zurück."""
    with open(filepath, encoding="utf-8") as f:
        entries = json.load(f)

    to_geocode = [e for e in entries if needs_geocoding(e)]
    if not to_geocode:
        return 0

    print(f"\n  {filepath.name}: {len(to_geocode)}/{len(entries)} Einträge mit 0,0-Koordinaten")
    geocoded_count = 0

    for i, entry in enumerate(to_geocode):
        addr = entry.get("address", {})
        street = addr.get("street", "")
        postal_code = addr.get("postal_code", "")
        city = addr.get("city", "")
        country = addr.get("country", "DE")
        name = entry.get("name", "?")

        print(f"    [{i+1}/{len(to_geocode)}] {name} ({city}) ...", end=" ", flush=True)

        if not city:
            print("übersprungen (keine Stadt)")
            continue

        if dry_run:
            print("DRY-RUN")
            geocoded_count += 1
            continue

        lat, lng = geocode_address(street, postal_code, city, country)
        if lat != 0.0 or lng != 0.0:
            entry["coordinates"]["lat"] = lat
            entry["coordinates"]["lng"] = lng
            geocoded_count += 1
            print(f"✓ ({lat:.4f}, {lng:.4f})")
        else:
            print("✗ keine Koordinaten gefunden")

    if not dry_run and geocoded_count > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    return geocoded_count


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    file_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--file"):
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                file_filter = sys.argv[idx + 1]

    print("=== Geocode-Tool (Nominatim direkt) ===")
    if dry_run:
        print("Modus: DRY-RUN (keine Änderungen)")
    print()

    json_files = sorted(UNCHECKED_DIR.glob("*.json"))
    if file_filter:
        json_files = [f for f in json_files if file_filter.lower() in f.stem.lower()]
        if not json_files:
            print(f"Keine Datei gefunden für Filter: {file_filter}")
            return

    total_geocoded = 0
    for filepath in json_files:
        count = geocode_file(filepath, dry_run)
        total_geocoded += count

    print(f"\n=== Fertig: {total_geocoded} Einträge geocodiert ===")

    if not dry_run and total_geocoded > 0:
        print("\nNächster Schritt: python -m scraper.tools.clean")


if __name__ == "__main__":
    main()
