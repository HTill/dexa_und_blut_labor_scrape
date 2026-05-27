"""Amedes Standorte Scraper — extrahiert alle DE-Standorte von standorte.html.

Usage:
    python -m scraper.scrapers.amedes.run
    Oder direkt: python scraper/scrapers/amedes/run.py

Extrahiert alle Standorte von https://www.amedes-group.com/unternehmen/standorte.html
und speichert sie nach data/unchecked/amedes.json.
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

BASE_URL = "https://www.amedes-group.com"
STANDORTE_URL = f"{BASE_URL}/unternehmen/standorte.html"

rk = RequestKit(rate=0.5, retries=3)
geo_rk = RequestKit(rate=1.2, retries=3)
dk = DataKit("amedes")

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


def parse_phone_text(text: str) -> str | None:
    """Extrahiert Telefonnummer aus Text wie 'Telefon 0800 123456'."""
    # Ersetze non-breaking spaces
    text = text.replace('\xa0', ' ')
    
    # Suche nach Telefonnummern mit verschiedenen Formaten
    # Format: Telefon 0800 123456 oder Tel: +49(0)123/456789
    match = re.search(r'(?:Telefon|Tel\.?|Fax|Telefax)\s*[:\s]*([+]?[\d\s\-/()]+)', text, re.IGNORECASE)
    if match:
        phone = match.group(1)
        # Bereinige die Telefonnummer
        phone = phone.replace('(', '').replace(')', '').replace('/', '').replace(' ', '').replace('-', '')
        if phone and len(phone) >= 7:  # Mindestens 7 Ziffern für eine gültige Nummer
            return phone
    return None


def parse_email_text(text: str) -> str | None:
    """Extrahiert E-Mail aus Text mit data-mailto-token oder direkter E-Mail."""
    # Ersetze non-breaking spaces
    text = text.replace('\xa0', ' ')
    
    # Suche nach data-mailto-token Attribut
    match = re.search(r'data-mailto-token="[^"]+".*?>([^<]+)\(at\)([^<]+)', text)
    if match:
        return f"{match.group(1)}@{match.group(2)}"
    
    # Suche nach normaler E-Mail
    match = re.search(r'[\w\.\-]+@[\w\.\-]+\.[a-zA-Z]{2,}', text)
    if match:
        return match.group(0)
    return None


def parse_website_text(text: str) -> str | None:
    """Extrahiert Website-URL aus Text."""
    # Ersetze non-breaking spaces
    text = text.replace('\xa0', ' ')
    
    match = re.search(r'(?:Internet|Website|www\.|http[s]?://)([^\s<>"]+)', text, re.IGNORECASE)
    if match:
        url = match.group(1)
        if not url.startswith('http'):
            url = f"https://{url}" if url.startswith('www.') else f"https://{url}"
        return url
    return None


def extract_address_from_div(div: BeautifulSoup) -> tuple[str, str, str]:
    """Extrahiert Adresse aus dem address Div."""
    address_text = div.get_text(' ', strip=True)
    
    # Behandle Zweigpraxis - nimm nur die erste Adresse
    if 'Zweigpraxis' in address_text or 'Zweigstelle' in address_text:
        # Extrahiere nur den Teil vor Zweigpraxis
        match = re.search(r'^(.+?)(?:\s+Zweigpraxis|\s+Zweigstelle)', address_text, re.IGNORECASE)
        if match:
            address_text = match.group(1).strip()
    
    # Entferne alle Kontaktdaten (Telefon, Internet, E-Mail, etc.)
    # Ersetze durch ein spezielles Trennzeichen
    cleaned_text = re.sub(r'(?:Telefon|Tel\.?|Fax|Telefax|Internet|E-Mail|E-mail|www\.)[^\d]*', '|||', address_text, flags=re.IGNORECASE)
    
    # Suche nach PLZ (5 Ziffern) und Stadt vor dem Trennzeichen oder Ende
    match = re.search(r'^(.+?)(\d{5})\s+([^\d\|]+)', cleaned_text)
    if match:
        street = match.group(1).strip()
        postal_code = match.group(2)
        city = match.group(3).strip()
        
        # Bereinige Straße
        street = re.sub(r'\s+', ' ', street)
        street = re.sub(r'[,\.;:]$', '', street)
        
        return street, postal_code, city
    
    # Alternative: Suche nach PLZ und Stadt am Ende (ohne Kontaktdaten)
    match = re.search(r'(.+?)(\d{5})\s+([^\d]+)$', cleaned_text)
    if match:
        street = match.group(1).strip()
        postal_code = match.group(2)
        city = match.group(3).strip()
        
        # Bereinige Straße
        street = re.sub(r'\s+', ' ', street)
        street = re.sub(r'[,\.;:]$', '', street)
        
        return street, postal_code, city
    
    # Alternative: PLZ am Anfang
    match = re.match(r'^(\d{5})\s+(.+)$', cleaned_text)
    if match:
        return "", match.group(1), match.group(2)
    
    return address_text, "", ""


def extract_contact_from_div(div: BeautifulSoup, address_div: BeautifulSoup | None = None) -> tuple[str | None, str | None, str | None]:
    """Extrahiert Telefon, Fax und E-Mail aus dem contact Div und optional address Div."""
    contact_text = div.get_text(' ', strip=True)
    div_html = str(div)
    
    phone = parse_phone_text(contact_text)
    email = parse_email_text(div_html)
    website = parse_website_text(contact_text)
    
    # Falls keine Kontaktdaten gefunden wurden, suche auch im address Div
    if not phone and address_div:
        address_text = address_div.get_text(' ', strip=True)
        phone = parse_phone_text(address_text)
    
    if not email and address_div:
        address_html = str(address_div)
        email = parse_email_text(address_html)
    
    if not website and address_div:
        address_text = address_div.get_text(' ', strip=True)
        website = parse_website_text(address_text)
    
    return phone, email, website


def scrape_standorte() -> list:
    """Haupt-Scraping-Funktion für die Standorte-Seite."""
    html = rk.get(STANDORTE_URL).text
    soup = BeautifulSoup(html, "lxml")
    
    providers = []
    seen_names = set()
    
    # Finde alle location_details Divs
    location_divs = soup.find_all("div", {"class": "location_details"})
    
    for div in location_divs:
        # Extrahiere Name aus h2
        h2 = div.find("h2")
        if not h2:
            continue
        
        name = h2.get_text(strip=True)
        
        # Deduplizierung
        if name in seen_names:
            continue
        seen_names.add(name)
        
        # Extrahiere Adresse
        address_div = div.find("div", {"class": "address"})
        if not address_div:
            continue
        
        street, postal_code, city = extract_address_from_div(address_div)
        if not street or not city:
            continue
        
        # Extrahiere Kontakt
        contact_div = div.find("div", {"class": "contact"})
        phone, email, website = None, None, None
        if contact_div:
            phone, email, website = extract_contact_from_div(contact_div, address_div)
        else:
            # Falls kein contact Div, versuche aus address Div zu extrahieren
            phone, email, website = extract_contact_from_div(address_div)
        
        
        address_str = f"{street}, {postal_code} {city}, Germany"
        lat, lng = geocode(address_str)
        
        # Erstelle Provider-Eintrag
        provider = dk.provider(
            id=f"amedes-{name.lower().replace(' ', '-').replace('ä', 'a').replace('ö', 'o').replace('ü', 'u').replace('ß', 'ss')}",
            name=name,
            category="blutlabor",
            address=dk.address(
                street=street,
                postal_code=postal_code,
                city=city,
                country="DE"
            ),
            coordinates=dk.coordinates(lat=lat, lng=lng),
            contact=dk.contact(phone=phone, website=website, email=email) if phone or website or email else None,
            services=[dk.svc.BLOOD_SELF_PAYER.value],
            self_payer=True,
            verified=False,
            notes="Standort der amedes-Gruppe. Selbstzahler-Option für Bluttests anzufragen.",
            docs=(
                "Annahme: Als großes Labornetzwerk bietet amedes in der Regel "
                "Blutuntersuchungen auch für Selbstzahler an. "
                "Dies sollte telefonisch verifiziert werden."
            ),
            source=[STANDORTE_URL],
        )
        providers.append(provider)
    
    return providers


def main() -> None:
    print(f"=== Amedes Scraper: {STANDORTE_URL} ===\n")
    
    providers = scrape_standorte()
    
    print(f"Extrahiert: {len(providers)} Standorte")
    
    if providers:
        dk.save(providers)
        print(f"Gespeichert: data/unchecked/amedes.json")
        
        # Zeige erste 3 als Preview
        for p in providers[:3]:
            print(f"  - {p.name} ({p.address.city})")
    else:
        print("Keine Standorte gefunden!")


if __name__ == "__main__":
    main()
