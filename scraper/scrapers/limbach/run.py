"""Limbach Gruppe Scraper — extrahiert alle Labor- und Blutentnahme-Standorte via API.

Usage:
    python -m scraper.scrapers.limbach.run
    Oder direkt: python scraper/scrapers/limbach/run.py

Nutzt die REST API unter https://www.limbachgruppe.com/api/v1/laboratories
und speichert die Ergebnisse nach data/unchecked/limbach.json.
Nur Standorte der Kategorien "Labor" (uid 7) und "Blutentnahme" (uid 37)
werden als blutlabor übernommen — Praxen ohne Labordiagnostik werden ignoriert.
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import json

from scraper.tools.data_kit import DataKit
from scraper.tools.request_kit import RequestKit

API_URL = "https://www.limbachgruppe.com/api/v1/laboratories"
BASE_URL = "https://www.limbachgruppe.com"
CATEGORY_LABOR = 7
CATEGORY_BLUTENTNAHME = 37

COUNTRY_MAP = {
    "Deutschland": "DE",
    "Österreich": "AT",
    "Schweiz": "CH",
}

rk = RequestKit(proxy=None, rate=0.5, retries=3)
dk = DataKit("limbach")


def fetch_lab_locations() -> list[dict]:
    """Ruft alle Labor-Standorte (category=7) via API ab."""
    resp = rk.get(f"{API_URL}?category={CATEGORY_LABOR}")
    data = json.loads(resp.text)
    return data.get("elements", [])


def fetch_blutentnahme_locations() -> list[dict]:
    """Ruft alle Blutentnahme-Standorte (category=37) via API ab."""
    resp = rk.get(f"{API_URL}?category={CATEGORY_BLUTENTNAHME}")
    data = json.loads(resp.text)
    return data.get("elements", [])


def map_country(raw: str) -> str:
    """Mapped den ausgeschriebenen Ländernamen auf das ISO-Kürzel (DE/AT/CH)."""
    return COUNTRY_MAP.get(raw, "DE")


def build_provider(entry: dict) -> dict | None:
    """Baut einen Provider-Eintrag aus einem API-Labor-Eintrag."""
    uid = entry.get("uid")
    name = entry.get("name")
    lat = entry.get("latitude")
    lng = entry.get("longitude")
    address = entry.get("address", "")
    zip_code = entry.get("zip", "")
    city = entry.get("city", "")
    country = entry.get("country", "Deutschland")
    phone = entry.get("phone")
    email = entry.get("email")
    website = entry.get("website")

    if not uid or not name or not lat or not lng:
        return None

    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return None

    if not address or not city:
        return None

    category = "blutlabor"

    # Immer Bluttest Selbstzahler als Service setzen (Annahme)
    services = [dk.svc.BLOOD_SELF_PAYER.value]

    contact_fields = {}
    if phone:
        contact_fields["phone"] = phone
    if website:
        contact_fields["website"] = website
    if email:
        contact_fields["email"] = email
    contact = dk.contact(**contact_fields) if contact_fields else None

    provider = dk.provider(
        id=f"limbach-{uid}",
        name=name,
        category=category,
        address=dk.address(
            street=address,
            postal_code=zip_code,
            city=city,
            country=map_country(country),
        ),
        coordinates=dk.coordinates(lat=lat, lng=lng),
        contact=contact,
        services=services,
        self_payer=True,
        verified=False,
        docs=(
            "Annahme: Laborstandorte der Limbach Gruppe bieten in der Regel "
            "ein breites Spektrum an Selbstzahler-Bluttests an "
            "(Allergie-Diagnostik, Autoimmun-Diagnostik, Diabetes-Checks etc.). "
            "Exaktes Angebot und Preise bitte auf der jeweiligen Labor-Website "
            "prüfen oder telefonisch erfragen."
        ),
        source=["https://www.limbachgruppe.com/ihr-laborpartner/die-gruppe/standorte/"],
    )
    return provider


def main() -> None:
    print("=== Limbach Gruppe Scraper ===\n")

    lab_elements = fetch_lab_locations()
    blut_elements = fetch_blutentnahme_locations()

    seen_ids = set()
    all_elements = []

    for entry in lab_elements + blut_elements:
        uid = entry.get("uid")
        if uid in seen_ids:
            continue
        seen_ids.add(uid)
        all_elements.append(entry)

    providers = []
    for entry in all_elements:
        provider = build_provider(entry)
        if provider:
            providers.append(provider)

    print(f"API lieferte: {len(lab_elements)} Labore + {len(blut_elements)} Blutentnahme-Standorte")
    print(f"Nach Dedup: {len(all_elements)} eindeutige Standorte")
    print(f"Übernommen: {len(providers)} Provider\n")

    if providers:
        # Gruppiere nach Land für Übersicht
        by_country = {}
        for p in providers:
            country = p.address.country
            by_country.setdefault(country, []).append(p)

        for country_code in sorted(by_country):
            locs = by_country[country_code]
            print(f"  {country_code}: {len(locs)} Standorte")

        dk.save(providers)
        print(f"\nGespeichert: data/unchecked/limbach.json")

        # Zeige erste 5 als Preview
        print("\nPreview:")
        for p in providers[:5]:
            print(f"  - {p.name} ({p.address.city}, {p.address.country})")
    else:
        print("Keine Standorte gefunden!")


if __name__ == "__main__":
    main()
