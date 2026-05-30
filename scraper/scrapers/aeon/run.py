"""Aeon Standorte Scraper — extrahiert DEXA-Partnerstandorte von aeon.life.

Usage:
    python -m scraper.scrapers.aeon.run
    Oder direkt: python scraper/scrapers/aeon/run.py

Extrahiert alle Standorte von https://aeon.life/de-de/standorte/
aus dem Nuxt 3 SSR Payload (Storyblok CMS) und speichert sie nach
data/unchecked/aeon.json.
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import json
import re

from scraper.tools.data_kit import DataKit
from scraper.tools.request_kit import RequestKit
from scraper.tools.geocode import geocode_address

BASE_URL = "https://aeon.life"
STANORTE_URL = f"{BASE_URL}/de-de/standorte/"

rk = RequestKit(rate=0.5, retries=3)
dk = DataKit("aeon")

CH_CITIES = {"rheinfelden", "basel", "bern", "genf", "zuerich", "zurich"}


def _resolve_path(payload: list, start_idx: int):
    """Resolve a reference chain from a starting index in the payload.

    Walks references step by step, unwrapping Nuxt reactive wrappers
    like ['ShallowReactive', ref]. Returns the fully resolved value.
    """
    memo = {}
    resolving = set()

    def follow(idx):
        if idx in memo:
            return memo[idx]
        if idx in resolving:
            return None
        if not (0 <= idx < len(payload)):
            return idx

        resolving.add(idx)
        node = payload[idx]
        if isinstance(node, int):
            result = follow(node)
        elif isinstance(node, list) and len(node) == 2 and isinstance(node[0], str):
            result = follow(node[1])
        elif isinstance(node, list):
            result = [follow(i) if isinstance(i, int) else i for i in node]
        elif isinstance(node, dict):
            result = {k: follow(v) if isinstance(v, int) else v for k, v in node.items()}
        else:
            result = node
        resolving.discard(idx)
        memo[idx] = result
        return result

    return follow(start_idx)


def parse_address(address: str) -> tuple:
    """Parse 'Strasse 5, 1234 Stadt' into (street, plz, city)."""
    match = re.match(r"^(.+),\s*(\d{4,5})\s+(.+)$", address)
    if match:
        return match.group(1).strip(), match.group(2), match.group(3).strip()
    return address, "", ""


def country_from_city(city: str) -> str:
    """Determine country from city name."""
    city_lower = city.lower()
    for cc in CH_CITIES:
        if cc in city_lower:
            return "CH"
    return "DE"


def extract_detail_link(card: dict) -> str | None:
    """Extract link from a location card — detail page preferred, booking as fallback."""
    fallback = None
    for btn_key in ("secondaryButton", "primaryButton"):
        btn = card.get(btn_key)
        if isinstance(btn, list) and len(btn) == 1 and isinstance(btn[0], dict):
            btn = btn[0]
        if not isinstance(btn, dict):
            continue
        link = btn.get("link")
        if not isinstance(link, dict):
            continue
        url = link.get("cached_url", "")
        if not url:
            continue
        # Detail page (relative path) is preferred
        if url.startswith("/") and "booking." not in url:
            return f"{BASE_URL}{url}"
        # Booking or absolute URL as fallback
        if url.startswith("https://"):
            fallback = url
    return fallback


def scrape_aeon() -> list:
    """Main scraping function — parse Nuxt SSR payload for location cards."""
    print(f"Fetching {STANORTE_URL} ...")
    html = rk.get(STANORTE_URL).text

    match = re.search(
        r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    )
    if not match:
        print("ERROR: __NUXT_DATA__ script not found in HTML")
        return []

    payload = json.loads(match.group(1))
    if not isinstance(payload, list):
        print("ERROR: unexpected payload format")
        return []

    print(f"Resolving Nuxt payload ({len(payload)} elements) ...")

    meta = payload[1]
    if not isinstance(meta, dict):
        print("ERROR: metadata not a dict")
        return []

    data_ref = meta.get("data")
    if not isinstance(data_ref, int):
        print("ERROR: data ref not found in metadata")
        return []

    page_data = _resolve_path(payload, data_ref)
    if not isinstance(page_data, dict):
        print(f"ERROR: resolved page data is {type(page_data).__name__}")
        return []

    standorte_entry = None
    for key, value in page_data.items():
        if "standorte" in key:
            if isinstance(value, int):
                standorte_entry = _resolve_path(payload, value)
            else:
                standorte_entry = value
            break

    if not isinstance(standorte_entry, dict):
        print("ERROR: standorte page data not found")
        return []

    content = standorte_entry.get("content") or {}
    if isinstance(content, int):
        content = _resolve_path(payload, content) or {}

    if not isinstance(content, dict):
        print("ERROR: no content found")
        return []

    body = content.get("body")
    if isinstance(body, int):
        body = _resolve_path(payload, body)

    if not isinstance(body, list):
        print("ERROR: no body components found")
        return []

    providers = []
    current_country = None
    seen_cities = set()

    for component in body:
        if not isinstance(component, dict):
            continue

        comp_type = component.get("component", "")

        if comp_type == "TextSection":
            title = component.get("title", "")
            if "Schweiz" in title:
                current_country = "CH"
            elif "Deutschland" in title:
                current_country = "DE"

        elif comp_type == "cards-in-columns-section":
            cards = component.get("cards")
            if not isinstance(cards, list):
                continue

            for card in cards:
                if not isinstance(card, dict):
                    continue
                if card.get("component") != "location-card":
                    continue

                name = card.get("title", "")
                address_raw = card.get("subtitle", "")

                if not name or not address_raw:
                    continue

                street, postal_code, city = parse_address(address_raw)
                if not city:
                    continue

                addr_key = f"{city.lower()}|{street.lower()}"
                if addr_key in seen_cities:
                    continue
                seen_cities.add(addr_key)

                country = current_country or country_from_city(city)
                website = extract_detail_link(card)

                city_slug = (
                    name.lower()
                    .replace(" ", "-")
                    .replace("ü", "u")
                    .replace("ä", "a")
                    .replace("ö", "o")
                    .replace("ß", "ss")
                    .replace("é", "e")
                )

                provider = dk.provider(
                    id=f"aeon-{city_slug}",
                    name=f"Aeon {name}",
                    category="dexa",
                    address=dk.address(
                        street=street,
                        postal_code=postal_code,
                        city=city,
                        country=country,
                    ),
                    coordinates=dk.coordinates(lat=0, lng=0),
                    contact=dk.contact(website=website or BASE_URL),
                    services=[dk.svc.DEXA_BODY_COMP.value],
                    self_payer=True,
                    verified=False,
                    docs=(
                        "Daten von aeon.life Standortseite. "
                        "DEXA Body Scan wird laut FAQ als optionale Zusatzleistung "
                        "(Dauer: ~10 min) zum MRI Check-up angeboten. "
                        "Selbstzahler: Kosten der Grundversicherung werden nicht uebernommen."
                    ),
                    source=[STANORTE_URL],
                )
                providers.append(provider)

    return providers


def main() -> None:
    print(f"=== Aeon Scraper: {STANORTE_URL} ===\n")

    providers = scrape_aeon()

    ch = sum(1 for p in providers if p.address.country == "CH")
    de = sum(1 for p in providers if p.address.country == "DE")
    print(f"Extrahiert: {len(providers)} Standorte (CH: {ch}, DE: {de})")

    if providers:
        print(f"\nGeocoding {len(providers)} Standorte ...")
        for i, p in enumerate(providers):
            addr = p.address
            lat, lng = geocode_address(addr.street, addr.postal_code, addr.city, addr.country)
            if lat != 0 or lng != 0:
                p.coordinates.lat = lat
                p.coordinates.lng = lng
                print(f"  [{i+1}/{len(providers)}] {p.name}: ({lat:.4f}, {lng:.4f})")
            else:
                print(f"  [{i+1}/{len(providers)}] {p.name}: ✗ keine Koordinaten")

        dk.save(providers)
        print(f"Gespeichert: data/unchecked/aeon.json")
        for p in providers:
            print(f"  - {p.name} ({p.address.city}, {p.address.country})")
    else:
        print("Keine Standorte gefunden!")


if __name__ == "__main__":
    main()
