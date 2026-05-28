"""LADR Facharztlabore Scraper — extrahiert Standorte von www.ladr.de.

Usage:
    python -m scraper.scrapers.ladr.run
    Oder direkt: python scraper/scrapers/ladr/run.py

Scraped die 18 Facharztlabor-Detailseiten unter
https://www.ladr.de/ein-starker-verbund/labor-vor-ort/facharztlabore/

Basislabore (Laborgemeinschaften) sind reine Probenannahmestellen für
niedergelassene Ärzte ohne Publikumsverkehr — daher nicht inkludiert.
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import base64
import re
from bs4 import BeautifulSoup

from scraper.tools.data_kit import DataKit
from scraper.tools.request_kit import RequestKit

BASE_URL = "https://www.ladr.de"
LABS_PATH = "/ein-starker-verbund/labor-vor-ort/facharztlabore"
SELF_PAYER_INFO_URL = "https://www.ladr.de/fuer-patientinnen/leistung/igel"

LOCATIONS = [
    ("baden-baden", "Baden-Baden"),
    ("berlin", "Berlin"),
    ("bernau", "Bernau"),
    ("braunschweig", "Braunschweig"),
    ("bremen", "Bremen"),
    ("celle", "Celle"),
    ("flintbek/kiel", "Flintbek/Kiel"),
    ("geesthacht", "Geesthacht"),
    ("hannover", "Hannover"),
    ("kaiserslautern", "Kaiserslautern"),
    ("koeln", "Köln"),
    ("leer", "Leer"),
    ("muenster", "Münster"),
    ("neuruppin", "Neuruppin"),
    ("paderborn", "Paderborn"),
    ("recklinghausen", "Recklinghausen"),
    ("ruedersdorf", "Rüdersdorf"),
    ("schuettorf", "Schüttorf"),
]

rk = RequestKit(rate=0.5, retries=3)
geo_rk = RequestKit(rate=1.5, retries=3)
dk = DataKit("ladr")

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


def decode_typo3_email(token: str, vector: int) -> str:
    """Dekodiert TYPO3s spam-geschützte Email (Base64 + ROTn)."""
    decoded = base64.b64decode(token).decode("ascii", errors="replace")
    if vector < 0:
        vector += 128
    size = (len(decoded) + 1) * 256
    result = []
    for char in decoded:
        i = size % 256
        for _ in range(0, 3, 1):
            i = (i + 1) % 256 if i < 128 else (i + 1) % 128
        result.append(chr(ord(char) - i))
        size -= 1
        size = size // 256
    return "".join(reversed(result))


def parse_address(text: str) -> tuple[str, str, str]:
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = BeautifulSoup(text, "lxml").get_text("\n").strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if len(lines) >= 2:
        street = lines[0]
        match = re.match(r"^(\d{5})\s+(.+)$", lines[1])
        if match:
            return street, match.group(1), match.group(2).strip()
    if len(lines) == 1:
        match = re.search(r"(\d{5})\s+([^\d].+)$", lines[0])
        if match:
            return (
                lines[0][:match.start()].strip(),
                match.group(1),
                match.group(2).strip(),
            )
    return "", "", ""


def parse_page(html: str, url: str) -> dict | None:
    """Extrahiert Name, Adresse, Telefon, Email und Koordinaten aus einer LADR-Detailseite."""
    soup = BeautifulSoup(html, "lxml")

    card_body = soup.select_one(".toideate-m-cardteaser-content-body")
    if not card_body:
        return None

    name_el = card_body.select_one("h3")
    name = name_el.get_text(strip=True) if name_el else None
    if not name:
        return None

    addr_span = card_body.select_one(".toideate-m-cardteaser-content-txt")
    if not addr_span:
        return None

    street, postal_code, city = parse_address(str(addr_span))
    if not street or not city:
        return None

    phone_link = card_body.select_one("a[href^='tel:']")
    phone = phone_link["href"].removeprefix("tel:").strip() if phone_link else None

    mail_link = card_body.select_one("a[data-mailto-token]")
    email = None
    if mail_link:
        token = mail_link.get("data-mailto-token", "")
        vector = int(mail_link.get("data-mailto-vector", 1))
        try:
            email = decode_typo3_email(token, vector)
        except Exception:
            pass

    # Koordinaten aus Google Maps Link extrahieren
    maps_link = card_body.select_one(".toideate-m-cardteaser-content-green--map")
    lat, lng = None, None
    if maps_link:
        href = maps_link.get("href", "")
        coords = extract_coords_from_maps_link(href)
        if coords:
            lat, lng = coords

    return {
        "name": name,
        "street": street,
        "postal_code": postal_code,
        "city": city,
        "phone": phone,
        "email": email,
        "url": url,
        "lat": lat,
        "lng": lng,
        "had_coords": lat is not None,
    }


def main() -> None:
    print(f"=== LADR Scraper: {BASE_URL}{LABS_PATH} ===\n")
    print(f"Standorte: {len(LOCATIONS)}")

    providers = []
    map_count = 0
    geo_count = 0
    for i, (slug, label) in enumerate(LOCATIONS):
        url = f"{BASE_URL}{LABS_PATH}/{slug}"
        print(f"  [{i+1}/{len(LOCATIONS)}] {label} ...", end=" ", flush=True)

        try:
            html = rk.get(url).text
        except Exception as e:
            print(f"(HTTP-Fehler: {e})")
            continue

        detail = parse_page(html, url)
        if not detail:
            print("(keine Adressdaten)")
            continue

        lat, lng = detail.get("lat"), detail.get("lng")
        if lat is None or lng is None:
            address_str = f"{detail['street']}, {detail['postal_code']} {detail['city']}, Germany"
            lat, lng = geocode(address_str)
            geo_count += 1
        else:
            map_count += 1

        provider = dk.provider(
            id=f"ladr-{slug.replace('/', '-')}",
            name=detail["name"],
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
                website=url,
                email=detail.get("email"),
            ) if detail["phone"] else None,
            services=[dk.svc.BLOOD_SELF_PAYER.value],
            self_payer=True,
            verified=False,
            docs=(
                "Annahme: LADR bietet unter 'Für Patienten > Leistung > IGeL' "
                "Selbstzahler-Untersuchungen an (IGeL = Individuelle Gesundheitsleistungen). "
                f"Preisübersicht unter {SELF_PAYER_INFO_URL} . "
                "Ob Blutentnahme für Selbstzahler an ALLEN Standorten möglich ist, "
                "sollte telefonisch verifiziert werden."
            ),
            source=[url],
        )
        providers.append(provider)
        print(f"\u2713 {provider.address.city}")

    print(f"\nExtrahiert: {len(providers)} Standorte")
    print(f"Geo-Quelle: {map_count} via Google Maps, {geo_count} via Nominatim")

    if providers:
        dk.save(providers)
        print(f"Gespeichert: data/unchecked/ladr.json")
    else:
        print("Keine Standorte extrahiert!")


if __name__ == "__main__":
    main()
