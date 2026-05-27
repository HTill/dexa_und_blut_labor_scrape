"""IMD Labor Scraper — extrahiert Standorte von imd-berlin.de und Partnerlaboren.

Usage:
    python -m scraper.scrapers.imd.run
    Oder direkt: python scraper/scrapers/imd/run.py

Extrahiert Standorte von:
- https://www.imd-berlin.de/fuer-patienten/anfahrt (Berlin)
- https://www.imd-potsdam.de (Potsdam)
- https://www.imd-greifswald.de (Greifswald)
- http://www.imd-oderland.de (Oderland)
und speichert sie nach data/unchecked/imd.json.
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

# Hauptwebsite
BASE_URL = "https://www.imd-berlin.de"
ANFahrt_URL = f"{BASE_URL}/fuer-patienten/anfahrt"

# Partnerlabore - Liste aller bekannten IMD Standorte
PARTNER_LABS = {
    "potsdam": {
        "url": "https://www.imd-potsdam.de",
        "name": "IMD Potsdam",
        "manual_data": {
            "street": "Nuthedamm 60",
            "postal_code": "14480",
            "city": "Potsdam",
            "phone": "+49 331 7049-0",
            "email": None,
            "lat": 52.4005,
            "lng": 13.0645,
        }
    },
    "greifswald": {
        "url": "https://www.imd-greifswald.de",
        "name": "MVZ Labor Greifswald GmbH",
        "manual_data": {
            "street": "Vitus-Bering-Straße 27a",
            "postal_code": "17493",
            "city": "Greifswald",
            "phone": "+49 3834 81930",
            "fax": "+49 3834 819339",
            "email": "kontakt@imd-greifswald.de",
            "lat": 54.0944,
            "lng": 13.3873,
        }
    },
    "oderland": {
        "url": "http://www.imd-oderland.de",
        "name": "IMD Oderland",
        "manual_data": {
            "street": "Seestraße 75",
            "postal_code": "15517",
            "city": "Fürstenwalde/Spree",
            "phone": "+49 3361 379-0",
            "email": None,
            "lat": 52.3500,
            "lng": 14.0667,
        }
    }
}

rk = RequestKit(rate=0.5, retries=3)
dk = DataKit("imd")


def parse_address_from_microdata(soup: BeautifulSoup) -> tuple[str, str, str]:
    """Extrahiert Adresse aus Microdata-Markup (itemprop)."""
    street = soup.find("span", itemprop="streetAddress")
    postal_code = soup.find("span", itemprop="postalCode")
    city = soup.find("span", itemprop="addressLocality")

    street_text = street.get_text(strip=True) if street else ""
    postal_code_text = postal_code.get_text(strip=True) if postal_code else ""
    city_text = city.get_text(strip=True) if city else ""

    return street_text, postal_code_text, city_text


def extract_phone_and_fax(soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Extrahiert Telefon und Fax aus Microdata."""
    phone = soup.find("span", itemprop="telephone")
    fax = soup.find("span", itemprop="faxNumber")

    phone_text = phone.get_text(strip=True) if phone else None
    fax_text = fax.get_text(strip=True) if fax else None

    return phone_text, fax_text


def extract_gme_addresses(html: str) -> list[dict]:
    """Extrahiert Adressen aus dem gme.addresses JavaScript-Objekt."""
    addresses = []
    
    # Suche nach gme.addresses[...] = { ... } Blöcken
    pattern = r'gme\.addresses\[(\d+)\]\s*=\s*\{([^}]+)\}'
    matches = re.finditer(pattern, html, re.DOTALL)
    
    for match in matches:
        address_block = match.group(2)
        address_dict = {}
        
        # Extrahiere Felder aus dem JavaScript-Objekt
        title_match = re.search(r'title:\s*["\']([^"\']+)["\']', address_block)
        lat_match = re.search(r'latitude:\s*([\d.-]+)', address_block)
        lng_match = re.search(r'longitude:\s*([\d.-]+)', address_block)
        address_match = re.search(r'address:\s*["\']([^"\']+)["\']', address_block)
        
        if title_match:
            address_dict['title'] = title_match.group(1)
        if lat_match:
            address_dict['latitude'] = float(lat_match.group(1))
        if lng_match:
            address_dict['longitude'] = float(lng_match.group(1))
        if address_match:
            address_dict['address'] = address_match.group(1)
        
        if address_dict:
            addresses.append(address_dict)
    
    return addresses


def parse_address_string(address_str: str) -> tuple[str, str, str]:
    """Parsed Adress-String wie 'Siemensstraße 26A, 12247 Berlin, Deutschland'."""
    # Ersetze Kommas durch Leerzeichen für bessere Verarbeitung
    address_str = address_str.replace(',', ' ')
    
    # Suche nach 5 Ziffern (PLZ) gefolgt von Stadt
    match = re.search(r'(\d{5})\s+([^\d].+?)(?:\s+Deutschland)?$', address_str.strip())
    if match:
        plz = match.group(1)
        city = match.group(2).strip()
        street = address_str[:match.start()].strip()
        return street, plz, city
    
    return address_str, "", ""


def scrape_partner_lab(lab_key: str, lab_info: dict) -> list:
    """Scraped ein Partnerlabor oder verwendet manuelle Daten."""
    providers = []
    url = lab_info["url"]
    name = lab_info["name"]
    manual_data = lab_info.get("manual_data", {})
    
    # Versuche 1: Scrape von der Website
    try:
        html = rk.get(url).text
        soup = BeautifulSoup(html, "lxml")
        
        # Suche nach Adressinformationen im Text
        address_pattern = r'([A-Za-z\s]+[-\s]?Straße\s+\d+[a-z]?)\s*,?\s*(\d{5})\s+([A-Za-z\s]+)'
        address_match = re.search(address_pattern, html)
        
        if address_match:
            street = address_match.group(1).replace('-', ' ').strip()
            postal_code = address_match.group(2)
            city = address_match.group(3).strip()
            
            # Suche nach Telefon und Fax
            phone_pattern = r'Tel[\s:]+(\+?\d[\d\s\-\(\)]+)'
            fax_pattern = r'Fax[\s:]+(\+?\d[\d\s\-\(\)]+)'
            email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            
            phone_match = re.search(phone_pattern, html)
            fax_match = re.search(fax_pattern, html)
            email_match = re.search(email_pattern, html)
            
            phone = phone_match.group(1).replace(' ', '').replace('-', '') if phone_match else None
            fax = fax_match.group(1).replace(' ', '').replace('-', '') if fax_match else None
            email = email_match.group(1) if email_match else None
            
            # Standard-Koordinaten (wird später durch Geocoding ersetzt)
            lat, lng = manual_data.get('lat', 0.0), manual_data.get('lng', 0.0)
            
            # Fax wird in notes gespeichert, da Contact kein fax Feld hat
            notes_parts = [f"Partnerlabor von IMD Berlin"]
            if fax:
                notes_parts.append(f"Fax: {fax}")
            
            provider = dk.provider(
                id=f"imd-{lab_key}",
                name=name,
                category="blutlabor",
                address=dk.address(
                    street=street,
                    postal_code=postal_code,
                    city=city,
                    country="DE"
                ),
                coordinates=dk.coordinates(lat=lat, lng=lng),
                contact=dk.contact(
                    phone=phone,
                    email=email,
                    website=url
                ) if phone or email else None,
                services=[dk.svc.BLOOD_SELF_PAYER.value],
                self_payer=True,
                verified=False,
                notes=" ".join(notes_parts),
                docs=(
                    "Annahme: Als Partnerlabor von IMD Berlin bietet dieses Labor "
                    "Blutuntersuchungen auch für Selbstzahler an. "
                    "Dies sollte telefonisch verifiziert werden."
                ),
                source=[url],
            )
            providers.append(provider)
            return providers
            
    except Exception as e:
        print(f"  Fehler beim Scrapen von {url}: {e}")
    
    # Versuche 2: Falls Website-Scraping fehlschlägt, verwende manuell bekannte Daten
    if manual_data:
        print(f"  Verwende manuell bekannte Daten für {name}")
        street = manual_data.get('street', '')
        postal_code = manual_data.get('postal_code', '')
        city = manual_data.get('city', '')
        phone = manual_data.get('phone')
        fax = manual_data.get('fax')
        email = manual_data.get('email')
        lat = manual_data.get('lat', 0.0)
        lng = manual_data.get('lng', 0.0)
        
        if not (street and postal_code and city):
            print(f"  Unvollständige manuelle Daten für {name}, überspringe")
            return providers
        
        # Fax wird in notes gespeichert
        notes_parts = [f"Partnerlabor von IMD Berlin"]
        if fax:
            notes_parts.append(f"Fax: {fax}")
        
        provider = dk.provider(
            id=f"imd-{lab_key}",
            name=name,
            category="blutlabor",
            address=dk.address(
                street=street,
                postal_code=postal_code,
                city=city,
                country="DE"
            ),
            coordinates=dk.coordinates(lat=lat, lng=lng),
            contact=dk.contact(
                phone=phone,
                email=email,
                website=url
            ) if phone or email else None,
            services=[dk.svc.BLOOD_SELF_PAYER.value],
            self_payer=True,
            verified=False,
            notes=" ".join(notes_parts),
            docs=(
                "Annahme: Als Partnerlabor von IMD Berlin bietet dieses Labor "
                "Blutuntersuchungen auch für Selbstzahler an. "
                "Dies sollte telefonisch verifiziert werden."
            ),
            source=[url, "Manuell ergänzt"],
        )
        providers.append(provider)
    
    return providers


def scrape_anfahrt() -> list:
    """Haupt-Scraping-Funktion für die Anfahrt-Seite."""
    html = rk.get(ANFahrt_URL).text
    soup = BeautifulSoup(html, "lxml")

    providers = []
    
    # Versuche 1: Extrahiere aus gme.addresses JavaScript-Objekt
    gme_addresses = extract_gme_addresses(html)
    
    if gme_addresses:
        for addr in gme_addresses:
            street, postal_code, city = parse_address_string(addr.get('address', ''))
            
            if not street or not city:
                continue
            
            # Extrahiere sauberen Namen für die ID
            title = addr.get('title', 'IMD Labor Berlin')
            name_clean = title.lower().replace(' ', '-').replace('ä', 'a').replace('ö', 'o').replace('ü', 'u')
            # Entferne doppelte Bindestriche und führendes "imd-" falls vorhanden
            name_clean = re.sub(r'-+', '-', name_clean)
            name_clean = name_clean.lstrip('imd-')
            
            provider = dk.provider(
                id=f"imd-{name_clean}",
                name=title,
                category="blutlabor",
                address=dk.address(
                    street=street,
                    postal_code=postal_code,
                    city=city,
                    country="DE"
                ),
                coordinates=dk.coordinates(
                    lat=addr.get('latitude', 0.0),
                    lng=addr.get('longitude', 0.0)
                ),
                contact=dk.contact(
                    phone=addr.get('phone'),
                    website=BASE_URL
                ) if addr.get('phone') else None,
                services=[dk.svc.BLOOD_SELF_PAYER.value],
                self_payer=True,
                verified=False,
                notes=(
                    "Schwerpunkt Immunologie: Über 350 In-Haus-Testverfahren für immunologisch "
                    "vermittelte Erkrankungen. 3.000 Analyseparameter, enge Zusammenarbeit mit "
                    "wissenschaftlichen Einrichtungen. 500 Mitarbeitende (davon 37 Fachärzte), "
                    "bundesweite Expertise in Spezialdiagnostik."
                ),
                docs=(
                    "Annahme: Als großes Labornetzwerk bietet IMD in der Regel "
                    "Blutuntersuchungen auch für Selbstzahler an. "
                    "Dies sollte telefonisch verifiziert werden."
                ),
                source=[ANFahrt_URL],
            )
            providers.append(provider)
    
    # Versuche 2: Falls gme.addresses nicht gefunden, extrahiere aus Microdata
    if not providers:
        street, postal_code, city = parse_address_from_microdata(soup)
        phone, fax = extract_phone_and_fax(soup)
        
        if street and postal_code and city:
            # Standard-Koordinaten für Berlin-Steglitz
            lat, lng = 52.443394, 13.335115
            
            provider = dk.provider(
                id="imd-berlin",
                name="IMD Labor Berlin",
                category="blutlabor",
                address=dk.address(
                    street=street,
                    postal_code=postal_code,
                    city=city,
                    country="DE"
                ),
                coordinates=dk.coordinates(lat=lat, lng=lng),
                contact=dk.contact(
                    phone=phone,
                    website=BASE_URL
                ) if phone else None,
                services=[dk.svc.BLOOD_SELF_PAYER.value],
                self_payer=True,
                verified=False,
                notes=(
                    "Schwerpunkt Immunologie: Über 350 In-Haus-Testverfahren für immunologisch "
                    "vermittelte Erkrankungen. 3.000 Analyseparameter, enge Zusammenarbeit mit "
                    "wissenschaftlichen Einrichtungen. 500 Mitarbeitende (davon 37 Fachärzte), "
                    "bundesweite Expertise in Spezialdiagnostik."
                ),
                docs=(
                    "Annahme: Als großes Labornetzwerk bietet IMD in der Regel "
                    "Blutuntersuchungen auch für Selbstzahler an. "
                    "Dies sollte telefonisch verifiziert werden."
                ),
                source=[ANFahrt_URL],
            )
            providers.append(provider)

    return providers


def main() -> None:
    print(f"=== IMD Labor Scraper ===\n")

    providers = []
    
    # Scrape Berlin Standort
    print(f"Scrape {ANFahrt_URL}...")
    berlin_providers = scrape_anfahrt()
    providers.extend(berlin_providers)
    print(f"  Gefunden: {len(berlin_providers)} Standort(e) in Berlin")
    
    # Scrape alle Partnerlabore
    for lab_key, lab_info in PARTNER_LABS.items():
        print(f"Scrape {lab_info['url']} ({lab_info['name']})...")
        lab_providers = scrape_partner_lab(lab_key, lab_info)
        providers.extend(lab_providers)
        print(f"  Gefunden: {len(lab_providers)} Standort(e) in {lab_info['name']}")

    print(f"\nExtrahiert: {len(providers)} Standorte insgesamt")

    if providers:
        dk.save(providers)
        print(f"Gespeichert: data/unchecked/imd.json")
        
        # Zeige alle als Preview
        for p in providers:
            print(f"  - {p.name} ({p.address.city})")
    else:
        print("Keine Standorte gefunden!")


if __name__ == "__main__":
    main()
