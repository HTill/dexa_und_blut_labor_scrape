"""Wisplinghoff Standorte-Scraper — extrahiert Labore von wisplinghoff.de.

Usage:
    python -m scraper.scrapers.wisplinghoff.run
    Oder direkt: python scraper/scrapers/wisplinghoff/run.py

Extrahiert Standort-Seiten aus der Navigation von wisplinghoff.de.
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import re
from bs4 import BeautifulSoup

from scraper.tools.data_kit import DataKit
from scraper.tools.request_kit import RequestKit

BASE_URL = "https://www.wisplinghoff.de"
STANDORT_URLS = [
    "/das-labor/standort-aachen",
    "/das-labor/standort-berlin-mpu",
    "/das-labor/standort-bonn",
    "/das-labor/standort-delmenhorst-mpu",
    "/das-labor/standort-frankfurt",
    "/das-labor/standort-herne",
    "/das-labor/standort-kempen",
    "/das-labor/standort-kempen-1",
]

rk = RequestKit(rate=1.0, retries=3)
geo_rk = RequestKit(rate=1.2, retries=3)
dk = DataKit("wisplinghoff")


def geocode(address_str: str) -> tuple[float, float]:
    try:
        resp = geo_rk.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address_str, "format": "json", "limit": 1},
            headers={"User-Agent": "DeXaBlutLaborScraper/1.0"},
        )
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass
    return 0.0, 0.0


def get_city_from_slug(slug: str) -> str:
    """Ratet den Stadtnamen aus dem URL-Slug."""
    parts = slug.replace("standort-", "").split("-")
    name = " ".join(p for p in parts if p != "mpu")
    return {"kempen": "Kempen", "kempen 1": "Schwäbisch Gmünd"}.get(name, name.title())


def parse_page(html: str) -> dict | None:
    """Parst Adresse, PLZ, Stadt, Telefon aus einer Standort-Detailseite."""
    soup = BeautifulSoup(html, "lxml")

    for p in soup.find_all("p"):
        strong = p.find("strong")
        if strong and "Kontaktdaten" in strong.get_text():
            texts = [t.strip() for t in p.stripped_strings if t.strip() != "Kontaktdaten"]

            street = ""
            postal_code = ""
            city = ""
            phone = ""

            for i, text in enumerate(texts):
                match = re.match(r"^(\d{5})\s+(.+)$", text)
                if match and i > 0 and texts[i-1] != "Tel.:":
                    postal_code = match.group(1)
                    city = match.group(2)
                    if not re.match(r"^(Labor|MVZ|Dr\.|Prof\.)", texts[i-1]):
                        street = texts[i-1]
                elif re.match(r"^Tel\.:?\s", text):
                    phone = re.sub(r"^Tel\.:?\s*", "", text)
                elif re.match(r"^0\d", text) and not phone:
                    phone = text

            if street and city:
                return {
                    "street": street,
                    "postal_code": postal_code,
                    "city": city,
                    "phone": phone or None,
                }

    return None


def main() -> None:
    print(f"=== Wisplinghoff Scraper: {BASE_URL} ===\n")
    print(f"Standort-Seiten: {len(STANDORT_URLS)}")

    providers = []
    for i, path in enumerate(STANDORT_URLS):
        url = f"{BASE_URL}{path}"
        slug = path.rsplit("/", 1)[-1] if path.endswith("/") else path.split("/")[-1]
        city_hint = get_city_from_slug(slug)

        print(f"  [{i+1}/{len(STANDORT_URLS)}] {city_hint} ...", end=" ", flush=True)

        try:
            html = rk.get(url).text
        except Exception:
            print("(HTTP-Fehler)")
            continue

        data = parse_page(html)
        if not data:
            print("(keine Adressdaten)")
            continue

        name = f"Labor Dr. Wisplinghoff {data['city']}"
        address_str = f"{data['street']}, {data['postal_code']} {data['city']}, Germany"
        lat, lng = geocode(address_str)

        provider = dk.provider(
            id=f"wisp-{slug}",
            name=name,
            category="blutlabor",
            address=dk.address(
                street=data["street"],
                postal_code=data["postal_code"],
                city=data["city"],
                country="DE",
            ),
            coordinates=dk.coordinates(lat=lat, lng=lng),
            contact=dk.contact(phone=data["phone"], website=url) if data["phone"] else None,
            services=[dk.svc.BLOOD_SELF_PAYER.value],
            self_payer=True,
            verified=False,
            docs=(
                "Wisplinghoff / Human Diagnostics Group bietet IGeL-Leistungen "
                "für Selbstzahler an (https://www.wisplinghoff.de/fuer-patienten/individuelle-vorsorge-igel). "
                "8 Standorte auf der Website gelistet, möglicherweise mehr über Partnerlabore."
            ),
            source=[url],
        )
        providers.append(provider)
        print(f"\u2713 {provider.address.city}")

    print(f"\nExtrahiert: {len(providers)} Standorte")

    if providers:
        dk.save(providers)
        print(f"Gespeichert: data/unchecked/wisplinghoff.json")
    else:
        print("Keine Standorte extrahiert!")


if __name__ == "__main__":
    main()
