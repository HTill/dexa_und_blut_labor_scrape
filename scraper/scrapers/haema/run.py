"""Haema Labor Scraper — extrahiert alle DE-Standorte von haema.de.

Usage:
    python -m scraper.scrapers.haema.run
    Oder direkt: python scraper/scrapers/haema/run.py

Extrahiert alle Standorte von https://www.haema.de/standorte/
und speichert sie nach data/unchecked/haema.json.
self_payer bleibt None für spätere Verifizierung.

Geocoding erfolgt via Nominatim (über RequestKit). Bei Rate-Limiting
werden Koordinaten auf 0.0 gesetzt; Geocoding kann später mit
--geocode wiederholt werden.
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import re
import sys as _sys

from bs4 import BeautifulSoup

from scraper.tools.data_kit import DataKit
from scraper.tools.request_kit import RequestKit

BASE_URL = "https://www.haema.de"
STANDORTE_URL = f"{BASE_URL}/standorte/"

rk = RequestKit(rate=0.5, retries=3)
geo_rk = RequestKit(rate=1.5, retries=3)
dk = DataKit("haema")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode(address_str: str) -> tuple[float, float]:
    address_str = address_str.replace("ß", "ss").replace("–", "-")
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


def parse_address_from_tag(text: str, city_hint: str) -> tuple[str, str, str]:
    """Parsed Adresse aus dem <p>-Tag der Detailseite.

    Formate:
      "Philippine-Welser-Straße 886150 Augsburg"
      "FacharztzentrumHildegard-von-Bingen-Straße 193053 Regensburg"
      "Aufseßplatz 212. Etage90459 Nürnberg"
    """
    m = re.search(r"(\d{5})\s+(.+)$", text)
    if not m:
        return text, "", city_hint

    plz = m.group(1)
    city = m.group(2).strip()
    before = text[: m.start()].strip()

    # Bauname trennen (z.B. "FacharztzentrumHildegard-von-Bingen-Straße")
    # Nutze den LETZTEN boundary (closest to street number)
    caps = list(re.finditer(r"[a-zäöüß0-9\x22\x27)\]\}][A-ZÄÖÜ]", before))
    if caps:
        cap = caps[-1]
        before = before[cap.start() + 1 :]

    # Stockwerk-Infos entfernen und Hausnummer behalten (z.B. "212. Etage" -> "21")
    before = re.sub(
        r"(\d+)\.\s*(Etage|OG|Stock|Obergeschoss)",
        lambda m: m.group(1)[:-1],
        before,
    )

    # Straßenname + Hausnummer extrahieren
    num = re.search(r"(\d+[a-zA-Z]?)", before)
    if num:
        street_num = num.group(1)
        street_name = before[: num.start()].strip()
        street = f"{street_name} {street_num}".strip()
    else:
        street = before.strip()

    return street, plz, city


def extract_location_links() -> list[dict]:
    """Extrahiert alle Standort-Links von der Übersichtsseite."""
    html = rk.get(STANDORTE_URL).text
    soup = BeautifulSoup(html, "lxml")

    locations = []
    for link in soup.select("a.bd-list-link[href*='/standorte/']"):
        href = link.get("href", "").strip()
        name = link.get_text(strip=True)
        if not href or not name:
            continue
        url = f"{BASE_URL}{href}" if href.startswith("/") else href
        locations.append({"name": name, "url": url})
    return locations


def scrape_location_detail(url: str, name_hint: str) -> dict | None:
    """Scraped eine Detailseite für Adresse und Telefon."""
    try:
        html = rk.get(url).text
    except Exception:
        return None

    soup = BeautifulSoup(html, "lxml")

    street, postal_code, city = "", "", ""

    # Adresse aus <p> innerhalb der article-intro / Kontakt-Sektion
    for p in soup.select(".article-intro p, .inner-container p"):
        p_text = p.get_text(strip=True)
        if re.search(r"\d{5}", p_text) and len(p_text) < 100:
            street, postal_code, city = parse_address_from_tag(p_text, name_hint)
            break

    # Fallback: kein <p> gefunden, nutze Seitentitel
    if not city:
        title = soup.find("title")
        if title:
            city_match = re.search(r"in\s+([A-Za-zÄÖÜäöüß\s]+)", title.get_text())
            if city_match:
                city = city_match.group(1).strip()
        if not city:
            city = name_hint

    # Telefon
    phone = None
    phone_link = soup.select_one("a[href^='tel:']")
    if phone_link:
        phone = phone_link.get_text(strip=True)

    # E-Mail
    email = None
    email_link = soup.select_one("a[href^='mailto:']")
    if email_link:
        email = email_link.get_text(strip=True)

    if not street and not city:
        return None

    return {
        "street": street,
        "postal_code": postal_code,
        "city": city,
        "phone": phone,
        "email": email,
    }


def main() -> None:
    do_geocode = "--geocode" in _sys.argv

    print(f"=== Haema Scraper: {STANDORTE_URL} ===")
    if do_geocode:
        print("Geocoding: EIN (Nominatim)\n")
    else:
        print("Geocoding: AUS (--geocode zum Aktivieren)\n")

    locations = extract_location_links()
    print(f"Standort-Links gefunden: {len(locations)}\n")

    providers = []
    for i, loc in enumerate(locations):
        print(f"  [{i+1}/{len(locations)}] {loc['name']} ...", end=" ", flush=True)

        detail = scrape_location_detail(loc["url"], loc["name"])

        if not detail:
            print("(keine Daten)")
            continue

        lat, lng = 0.0, 0.0
        if do_geocode:
            addr_parts = [detail["street"], detail["postal_code"], detail["city"]]
            address_str = ", ".join(p for p in addr_parts if p).strip()
            if address_str and not address_str.endswith("Germany"):
                address_str += ", Germany"
            if not address_str:
                address_str = f"{detail['city']}, Germany"
            lat, lng = geocode(address_str)

        provider = dk.provider(
            id=f"haema-{loc['name'].lower().replace(' ', '-').replace('--', '-')}",
            name=f"Haema {loc['name']}",
            category="blutlabor",
            address=dk.address(
                street=detail["street"],
                postal_code=detail["postal_code"],
                city=detail["city"],
                country="DE",
            ),
            coordinates=dk.coordinates(lat=lat, lng=lng),
            contact=dk.contact(
                phone=detail["phone"],
                website=loc["url"],
                email=detail["email"],
            ) if detail["phone"] or detail["email"] else None,
            services=[dk.svc.BLOOD_SELF_PAYER.value],
            self_payer=None,
            verified=False,
            docs=(
                "Haema bietet Selbstzahler-Bluttests und Gesundheitschecks an. "
                "Preise sind auf der Website einsehbar. "
                "Die Standorte sind bundesweit vertreten. "
                "Selbstzahler-Option sollte telefonisch verifiziert werden."
            ),
            source=[loc["url"]],
        )
        providers.append(provider)
        coord_str = f" ({lat:.4f}, {lng:.4f})" if do_geocode else ""
        print(f"✓ {provider.address.city}{coord_str}")

    print(f"\nExtrahiert: {len(providers)} Standorte")

    if providers:
        dk.save(providers)
        print(f"Gespeichert: data/unchecked/haema.json")
        for p in providers[:3]:
            print(f"  - {p.name} ({p.address.street}, {p.address.city})")
    else:
        print("Keine Standorte extrahiert!")


if __name__ == "__main__":
    main()
