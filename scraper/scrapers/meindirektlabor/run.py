"""MeinDirektlabor Standorte-Scraper — extrahiert Labore von meindirektlabor.de.

Usage:
    python -m scraper.scrapers.meindirektlabor.run
    Oder direkt: python scraper/scrapers/meindirektlabor/run.py

Scraped die Standort-Übersicht und Detailseiten von
https://www.meindirektlabor.de/standorte/
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import re
from bs4 import BeautifulSoup

from scraper.tools.data_kit import DataKit
from scraper.tools.request_kit import RequestKit

BASE_URL = "https://www.meindirektlabor.de"
OVERVIEW_URL = f"{BASE_URL}/standorte/"

rk = RequestKit(rate=1.0, retries=3)
geo_rk = RequestKit(rate=1.5, retries=3)
dk = DataKit("meindirektlabor")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode(address_str: str) -> tuple[float, float]:
    try:
        resp = geo_rk.get(
            NOMINATIM_URL,
            params={"q": address_str, "format": "json", "limit": 1},
            headers={"User-Agent": "DeXaBlutLaborScraper/1.0"},
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return 0.0, 0.0


def extract_coords_from_maps_link(html: str) -> tuple[float, float] | None:
    match = re.search(r'/@(-?\d+\.\d+),(-?\d+\.\d+),\d+z', html)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None


def parse_address(html: str) -> tuple[str, str, str]:
    """Extrahiert Straße, PLZ, Stadt aus <address>."""
    soup = BeautifulSoup(html, "lxml")
    addr_el = soup.select_one(".location-address address")
    if not addr_el:
        return "", "", ""

    text = addr_el.get_text("\n", strip=True)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if len(lines) >= 2:
        street = re.sub(r"\s*\(.*?\)", "", lines[0]).strip()
        match = re.match(r"^(\d{5})\s+(.+)$", lines[1])
        if match:
            return street, match.group(1), match.group(2)

    return "", "", ""


def parse_phone(html: str) -> str | None:
    """Extrahiert Telefonnummer aus Detailseite."""
    soup = BeautifulSoup(html, "lxml")
    phone_link = soup.select_one(".location-phone a")
    if phone_link:
        return phone_link.get_text(strip=True)
    phone_span = soup.select_one(".location-phone")
    if phone_span:
        return phone_span.get_text(strip=True).removeprefix("T:").strip()
    return None


def extract_overview() -> list[dict]:
    """Extrahiert alle Standort-Links von der Übersichtsseite."""
    html = rk.get(OVERVIEW_URL).text
    soup = BeautifulSoup(html, "lxml")

    locations = []
    for link in soup.select("a.location[data-title]"):
        title = link.get("data-title", "").strip()
        href = link.get("href", "").strip()

        if not title or not href:
            continue

        name = title.split(":", 1)[-1].strip() if ":" in title else title
        city = title.split(":", 1)[0].strip() if ":" in title else ""

        locations.append({
            "title": title,
            "name": name,
            "city_hint": city,
            "url": f"{BASE_URL}{href}" if href.startswith("/") else href,
        })

    return locations


def scrape_detail(url: str) -> dict | None:
    """Scraped eine Detailseite für Adresse, Telefon und Koordinaten."""
    try:
        html = rk.get(url).text
    except Exception:
        return None

    street, postal_code, city = parse_address(html)
    phone = parse_phone(html)
    coords = extract_coords_from_maps_link(html)

    if not street or not city:
        return None

    return {
        "street": street,
        "postal_code": postal_code,
        "city": city,
        "phone": phone,
        "lat": coords[0] if coords else None,
        "lng": coords[1] if coords else None,
        "had_coords": coords is not None,
    }


def main() -> None:
    print(f"=== MeinDirektlabor Scraper: {OVERVIEW_URL} ===\n")

    locations = extract_overview()
    print(f"Standorte gefunden: {len(locations)}")

    providers = []
    geocoded_count = 0
    for i, loc in enumerate(locations):
        print(f"  [{i+1}/{len(locations)}] {loc['title']} ...", end=" ", flush=True)
        detail = scrape_detail(loc["url"])

        if not detail:
            print("(keine Adressdaten)")
            continue

        lat, lng = detail.get("lat"), detail.get("lng")
        if lat is None or lng is None:
            address_str = f"{detail['street']}, {detail['postal_code']} {detail['city']}, Germany"
            lat, lng = geocode(address_str)
            geocoded_count += 1

        provider = dk.provider(
            id=f"mdl-{loc['name'].lower().replace(' ', '-')}",
            name=loc["name"],
            category="blutlabor",
            address=dk.address(
                street=detail["street"],
                postal_code=detail["postal_code"],
                city=detail["city"],
                country="DE",
            ),
            coordinates=dk.coordinates(lat=lat, lng=lng),
            contact=dk.contact(phone=detail["phone"], website=loc["url"]) if detail["phone"] else None,
            services=[dk.svc.BLOOD_SELF_PAYER.value],
            self_payer=True,
            verified=False,
            docs=(
                "MeinDirektlabor ist ein Selbstzahler-Labor — alle Tests werden "
                "ohne Überweisung direkt dem Patienten angeboten. "
                "Preise unter https://www.meindirektlabor.de/labortests/ "
                "einsehbar, nicht automatisch extrahierbar."
            ),
            source=[loc["url"]],
        )
        providers.append(provider)
        coord_src = "maps" if detail.get("had_coords") else "nominatim"
        print(f"✓ {provider.address.city} ({coord_src})")

    print(f"\nExtrahiert: {len(providers)} Standorte ({geocoded_count} via Geocoding)")
    print(f"Geo-Quelle: Google Maps Link > Nominatim")

    if providers:
        dk.save(providers)
        print(f"Gespeichert: data/unchecked/meindirektlabor.json")
    else:
        print("Keine Standorte extrahiert!")


if __name__ == "__main__":
    main()
