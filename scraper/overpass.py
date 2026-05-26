"""
Overpass API Scraper für Radiologie-Praxen in DACH.

Hinweis: Overpass unterscheidet NICHT zwischen Body Composition und reiner
Knochendichtemessung. Alle Ergebnisse müssen manuell nachgeprüft werden.
Jeder Eintrag bekommt source=["overpass"] und verified=False.
"""

import json
from pathlib import Path

import requests

from models import Address, Coordinates, Provider

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UNCHECKED_DIR = DATA_DIR / "unchecked"
OUTPUT_FILE = UNCHECKED_DIR / "overpass_dach.json"


def search_overpass(query: str, timeout: int = 30) -> list[dict]:
    """Führt eine Overpass-Query aus und gibt Elemente zurück."""
    resp = requests.get(OVERPASS_URL, params={"data": query}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("elements", [])


def _slugify(name: str, city: str) -> str:
    """Erzeugt einen einfachen Slug aus Name und Stadt."""
    return f"{name.lower().replace(' ', '-')}-{city.lower().replace(' ', '-')}"


def _build_provider(node: dict) -> Provider | None:
    """
    Konvertiert einen Overpass-Node in einen Provider.

    Returns None wenn der Node keine Adresse oder Koordinaten hat.
    """
    tags = node.get("tags", {})
    lat = node.get("lat")
    lng = node.get("lon")

    if lat is None or lng is None:
        return None

    name = tags.get("name")
    if not name:
        return None

    street = tags.get("addr:street", "")
    postal_code = tags.get("addr:postcode", "")
    city = tags.get("addr:city", "")
    country = tags.get("addr:country", "")

    # Ohne Adresse können wir den Eintrag nicht verifizieren
    if not city:
        return None

    # Falls country nicht gesetzt, aus dem Kontext ableiten
    if not country:
        country = "DE"  # Default, wird später korrigiert

    return Provider(
        id=_slugify(name, city),
        name=name,
        category="dexa",  # Overpass liefert nur Radiologie, aber unklar ob Body Comp
        address=Address(
            street=street or "Unbekannt",
            postal_code=postal_code or "00000",
            city=city,
            country=country,
        ),
        coordinates=Coordinates(lat=float(lat), lng=float(lng)),
        services=["Knochendichte oder Body Composition (manuell prüfen!)"],
        contact=None,
        self_payer=None,
        prices={},
        verified=False,
        notes="Overpass: Manuelle Prüfung nötig ob DEXA Body Composition angeboten wird.",
        source=["overpass"],
    )


def scrape_region(country_code: str = "DE") -> list[Provider]:
    """
    Scraped Radiologie-Praxen für ein Land.

    Args:
        country_code: ISO3166-1 Code (DE, AT, CH)

    Returns:
        Liste von Provider-Objekten
    """
    query = f"""
    [out:json];
    area["ISO3166-1"="{country_code}"];
    node["amenity"="doctors"]["healthcare:speciality"~"radiology"](area);
    out center;
    """
    nodes = search_overpass(query.strip())
    providers = []
    for node in nodes:
        provider = _build_provider(node)
        if provider:
            # Korrigiere country falls aus Tags ableitbar
            if provider.address.country != country_code:
                provider.address.country = country_code
            providers.append(provider)
    return providers


def main() -> None:
    """CLI-Einstieg: scraped DACH-Region und schreibt nach data/unchecked/overpass_dach.json."""
    all_providers = []

    for country in ["DE", "AT", "CH"]:
        print(f"Scrape {country}...", end=" ", flush=True)
        providers = scrape_region(country)
        print(f"{len(providers)} Einträge")
        all_providers.extend(providers)

    # Schreiben
    UNCHECKED_DIR.mkdir(parents=True, exist_ok=True)
    entries = [p.to_dict() for p in all_providers]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"✓ {len(entries)} Einträge nach {OUTPUT_FILE} geschrieben")
    print("⚠ JEDER Eintrag muss manuell geprüft werden (Body Comp vs. Knochendichte)!")


if __name__ == "__main__":
    main()
