"""
Overpass API Scraper für Radiologie-Praxen in DACH.

Hinweis: Overpass unterscheidet NICHT zwischen Body Composition und reiner
Knochendichtemessung. Alle Ergebnisse müssen manuell nachgeprüft werden.
Jeder Eintrag bekommt source=["overpass"] und verified=False.
"""

import requests

from scraper.tools.kit import Kit

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
kit = Kit("overpass_dach")


def search_overpass(query: str, timeout: int = 30) -> list[dict]:
    """Führt eine Overpass-Query aus und gibt Elemente zurück."""
    resp = requests.get(OVERPASS_URL, params={"data": query}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data.get("elements", [])


def _slugify(name: str, city: str) -> str:
    return f"{name.lower().replace(' ', '-')}-{city.lower().replace(' ', '-')}"


def _build_provider(node: dict):
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

    if not city:
        return None

    if not country:
        country = "DE"

    return kit.provider(
        id=_slugify(name, city),
        name=name,
        category="dexa",
        address=kit.address(
            street=street or "Unbekannt",
            postal_code=postal_code or "00000",
            city=city,
            country=country,
        ),
        coordinates=kit.coordinates(lat=float(lat), lng=float(lng)),
        services=[],
        verified=False,
        notes="Overpass: Manuelle Prüfung nötig ob DEXA Body Composition angeboten wird.",
        source=["overpass"],
    )


def scrape_region(country_code: str = "DE") -> list:
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
            if provider.address.country != country_code:
                provider.address.country = country_code
            providers.append(provider)
    return providers


def main() -> None:
    all_providers = []

    for country in ["DE", "AT", "CH"]:
        print(f"Scrape {country}...", end=" ", flush=True)
        providers = scrape_region(country)
        print(f"{len(providers)} Einträge")
        all_providers.extend(providers)

    kit.save(all_providers)
    print(f"✓ {len(all_providers)} Einträge nach data/unchecked/overpass_dach.json geschrieben")
    print("⚠ JEDER Eintrag muss manuell geprüft werden (Body Comp vs. Knochendichte)!")


if __name__ == "__main__":
    main()
