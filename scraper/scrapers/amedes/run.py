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
geo_rk = RequestKit(rate=1.5, retries=3)
dk = DataKit("amedes")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def geocode(address_str: str, country: str = "DE") -> tuple[float, float]:
    country_map = {"DE": "de", "AT": "at", "CH": "ch"}
    country_code = country_map.get(country, "de")

    # Strip parenthetical annotations before geocoding — Nominatim
    # does not understand "(Barkhof, Haus B, 6. Etage)"-style suffixes.
    query_str = re.sub(r'\s*\([^)]*\)', '', address_str).strip()

    try:
        resp = geo_rk.get(
            NOMINATIM_URL,
            params={
                "q": query_str,
                "format": "json",
                "limit": 1,
                "countrycodes": country_code,
            },
            headers={"User-Agent": "DeXaBlutLaborScraper/1.0 (amedes-scraper)"},
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as exc:
        print(f"      Geocode fehlgeschlagen für '{query_str}': {exc}")
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
    address_text = address_text.replace('\xa0', ' ')

    # Remove known non-address prefixes that leak into the street field.
    # These prefixes (company names, facility labels, "Zweigpraxis") appear
    # on the same <br>-separated line or as <p> wrappers before the actual
    # street line on the Amedes standorte page.
    for pattern in [
        r'\bamedes\s+Chirurgie\s+Kompetenznetz\s+Nord\b',
        r'\bamedes\s+Diabetologie\s+\w+\b',
        r'\bZweigpraxis\s*(?::|des\s+MVZ\s+[\w\s]+?)\b',
        r'\bZweigstelle\b',
        r'\bPrivatpraxis\b',
        r'\bim\s+[\w\s]*?Krankenhaus\b',
        r'\bMedizinzentrum\s+\w+\b',
        r'\bPoliklinik\s+am\s+[\w\s\-]+?\b(?=\s+\w+\d)',
    ]:
        match = re.search(pattern, address_text, re.IGNORECASE)
        if match:
            # Remove the prefix — it may span multiple words up to the street
            prefix_end = match.end()
            address_text = address_text[prefix_end:].strip()

    # Collapse contact info (phone, fax, email, URLs) into a pipe
    # separator so it does not get parsed as part of the city or street.
    address_text = re.sub(
        r'(?:Telefon|Tel\.?|Fax|Telefax|Internet|E-Mail|E-mail|www\.|https?://)\S*',
        '|||',
        address_text,
        flags=re.IGNORECASE,
    )

    # Remove known non-address trailing labels (only when after PLZ area).
    address_text = re.sub(
        r'\s*(?:Termin\s+vereinbaren|Ausgelagerte\s+Praxisräume).*$',
        '',
        address_text,
        flags=re.IGNORECASE,
    )

    # Only keep the portion before any contact separator.
    address_text = address_text.split('|||')[0].strip()

    # German postal code is exactly 5 digits. Street comes before,
    # city name after. City may contain hyphens and spaces.
    match = re.search(
        r'^(.+?)\s+(\d{5})\s+([A-Za-zÄÖÜäöüß][^\d]+?)\s*$',
        address_text,
    )
    if match:
        street = match.group(1).strip()
        postal_code = match.group(2)
        city = match.group(3).strip()

        street = re.sub(r'\s+', ' ', street)
        street = re.sub(r'[,\.;:]$', '', street)

        # Parens like "(Belgien)" or "(Barkhof, Haus B)" belong to
        # the street line in the original page; keep them there.
        city = re.sub(r'\s*\([^)]*\)\s*$', '', city).strip()
        return street, postal_code, city

    # Fallback: search for LAST 5-digit group in the remaining text.
    match = re.search(r'(.+?)(\d{5})\s+([^\d]+)$', address_text)
    if match:
        street = match.group(1).strip()
        postal_code = match.group(2)
        city = match.group(3).strip()
        street = re.sub(r'\s+', ' ', street)
        street = re.sub(r'[,\.;:]$', '', street)
        city = re.sub(r'\s*\([^)]*\)\s*$', '', city).strip()
        return street, postal_code, city

    # PLZ at the start (very unusual, kept as last resort).
    match = re.match(r'^(\d{5})\s+(.+)$', address_text)
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
        
        
        address_str = f"{street}, {postal_code}, {city}, Deutschland"
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
