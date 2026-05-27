"""Synlab LabLocator Scraper — extrahiert alle DE-Standorte von lablocator.

Usage:
    python -m scraper.scrapers.synlab.run
    Oder direkt: python scraper/scrapers/synlab/run.py

Extrahiert alle Standorte von https://www.synlab.de/lablocator
und speichert sie nach data/unchecked/synlab.json.
self_payer bleibt None für spätere Verifizierung.
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import re
from bs4 import BeautifulSoup

from scraper.tools.data_kit import DataKit
from scraper.tools.request_kit import RequestKit

BASE_URL = "https://www.synlab.de"
LABLOCATOR_URL = f"{BASE_URL}/lablocator"

rk = RequestKit(rate=0.5, retries=3)
dk = DataKit("synlab")


def parse_address(text: str) -> tuple[str, str, str]:
    """Parsed Adress-String wie 'Straße 123 86156 Stadt' -> (straße, plz, city)."""
    text = text.replace("<br>", " ").replace("<br/>", " ").replace("<br />", " ").strip()
    
    # Suche nach 5 Ziffern (PLZ) gefolgt von Stadt
    match = re.search(r"(\d{5})\s+([^\d].+)$", text)
    if match:
        plz = match.group(1)
        city = match.group(2).strip()
        street = text[:match.start()].strip()
        return street, plz, city
    
    # Alternative: PLZ am Anfang
    match = re.match(r"^(\d{5})\s+(.+)$", text)
    if match:
        return "", match.group(1), match.group(2)
    
    return text, "", ""


def extract_phone(item) -> str | None:
    """Extrahiert Telefonnummer aus dem Info-Bereich."""
    phone_td = item.select_one("td:-soup-contains('Telefon') + td")
    if phone_td:
        return phone_td.get_text(strip=True)
    return None


def extract_website(item) -> str | None:
    """Extrahiert relative URL aus 'Mehr zum Labor' Link."""
    link = item.select_one("a[href*='/lab/'], a[href*='/standort/']")
    if link and link.get("href"):
        href = link["href"].strip()
        if href.startswith("/"):
            return f"{BASE_URL}{href}"
        return href
    return None


def extract_name_and_type(item) -> tuple[str, str]:
    """Extrahiert Name (h4) und Typ (h5)."""
    name = item.select_one("h4")
    lab_type = item.select_one("h5")
    
    name_text = name.get_text(strip=True) if name else ""
    type_text = lab_type.get_text(strip=True) if lab_type else ""
    
    return name_text, type_text


def extract_address_text(item) -> str:
    """Extrahiert den Adress-Text aus dem address-text Div (ohne h4/h5)."""
    addr_div = item.select_one(".locations-list-item__address-text")
    if not addr_div:
        return ""
    
    # Clone um h4 und h5 zu entfernen
    for el in addr_div.find_all(["h4", "h5"]):
        el.decompose()
    
    # Jetzt den Text extrahieren
    text = addr_div.get_text(" ", strip=True)
    return text


def scrape_lablocator() -> list:
    """Haupt-Scraping-Funktion für die LabLocator-Seite."""
    html = rk.get(LABLOCATOR_URL).text
    soup = BeautifulSoup(html, "lxml")
    
    providers = []
    seen_uids = set()
    # Filter alle Humanmedizin-Labore (beide Varianten: mit und ohne Komma)
    items = soup.select("div.locations-list-item[data-uid][data-categories*='Humanmedizin']")
    
    for item in items:
        uid = item.get("data-uid")
        lat_str = item.get("data-lat")
        lng_str = item.get("data-lng")
        
        if not uid or not lat_str or not lng_str:
            continue
        
        # Deduplizierung: Jeder Standort kommt mehrmals im HTML vor
        if uid in seen_uids:
            continue
        seen_uids.add(uid)
        
        try:
            lat = float(lat_str)
            lng = float(lng_str)
        except ValueError:
            continue
        
        name, lab_type = extract_name_and_type(item)
        if not name:
            continue
        
        addr_text = extract_address_text(item)
        street, postal_code, city = parse_address(addr_text)
        
        if not street or not city:
            continue
        
        phone = extract_phone(item)
        website = extract_website(item)
        
        provider = dk.provider(
            id=f"synlab-{uid}",
            name=name,
            category="blutlabor",
            address=dk.address(
                street=street,
                postal_code=postal_code,
                city=city,
                country="DE"
            ),
            coordinates=dk.coordinates(lat=lat, lng=lng),
            contact=dk.contact(phone=phone, website=website) if phone or website else None,
            services=[dk.svc.BLOOD_SELF_PAYER.value],
            self_payer=True,
            verified=False,
            notes=f"Typ: {lab_type}" if lab_type else None,
            docs=(
                "Annahme: Aufgrund des Online-Auftritts von Synlab wird davon ausgegangen, "
                "dass in allen Humanmedizin-Laboren einfache Blutuntersuchungen "
                "auch für Selbstzahler angeboten werden. "
                "Dies sollte noch telefonisch verifiziert werden."
            ),
            source=[LABLOCATOR_URL],
        )
        providers.append(provider)
    
    return providers


def main() -> None:
    print(f"=== Synlab Scraper: {LABLOCATOR_URL} ===\n")
    
    providers = scrape_lablocator()
    
    print(f"Extrahiert: {len(providers)} Standorte")
    
    if providers:
        dk.save(providers)
        print(f"Gespeichert: data/unchecked/synlab.json")
        
        # Zeige erste 3 als Preview
        for p in providers[:3]:
            print(f"  - {p.name} ({p.address.city})")
    else:
        print("Keine Standorte gefunden!")


if __name__ == "__main__":
    main()
