"""
Manueller Scraper — Provider per Konsole erfassen.

Usage:
    python -m scraper.scrapers.manual.run
    Oder direkt: python scraper/scrapers/manual/run.py

Fragt Felder ab, validiert, hängt an data/unchecked/manual.json an.
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scraper.tools.data_kit import DataKit

dk = DataKit("manual")

CATEGORIES = {"d": "dexa", "b": "blutlabor", "db": "beide"}
COUNTRIES = ["DE", "AT", "CH"]


def prompt(msg: str, default: str = "") -> str:
    val = input(msg + (f" [{default}]" if default else "") + ": ").strip()
    return val if val else default


def prompt_category() -> str:
    print("Kategorien: (d) DEXA  (b) Blutlabor  (db) Beides")
    while True:
        c = prompt("Kategorie", "d").lower()
        if c in CATEGORIES:
            return CATEGORIES[c]
        print("  Ungültig. d, b oder db.")


def prompt_services() -> list[str]:
    print("Services (leer = fertig):")
    services = []
    for svc in sorted(dk.svc):
        if prompt(f"  {svc.value} (j/N)", "").lower() in ("j", "y"):
            services.append(svc.value)
    return services


def prompt_prices(services: list[str]) -> dict[str, str]:
    prices: dict[str, str] = {}
    if not services:
        return prices
    print("Preise (Enter = überspringen):")
    for svc in services:
        p = prompt(f"  {svc}")
        if p:
            prices[svc] = p
    return prices


def main() -> None:
    print("=== Manueller Provider-Eintrag ===\n")

    name = prompt("Name")
    if not name:
        print("Abgebrochen.")
        return

    category = prompt_category()
    services = prompt_services()
    street = prompt("Straße")
    postal_code = prompt("PLZ")
    city = prompt("Stadt")
    country = prompt("Land (DE/AT/CH)", "DE").upper()
    if country not in COUNTRIES:
        country = "DE"

    lat = float(prompt("Latitude", "0"))
    lng = float(prompt("Longitude", "0"))

    phone = prompt("Telefon") or None
    website = prompt("Website") or None
    email = prompt("E-Mail") or None

    self_payer_input = prompt("Selbstzahler? (j/N)", "").lower()
    self_payer = True if self_payer_input in ("j", "y") else None if not self_payer_input else False

    prices = prompt_prices(services)
    notes = prompt("Notizen") or None

    provider = dk.provider(
        id=f"{name.lower().replace(' ', '-')}-{city.lower().replace(' ', '-')}",
        name=name,
        category=category,
        address=dk.address(street=street, postal_code=postal_code, city=city, country=country),
        coordinates=dk.coordinates(lat=lat, lng=lng),
        services=services,
        contact=dk.contact(phone=phone, website=website, email=email) if (phone or website or email) else None,
        self_payer=self_payer,
        prices=prices,
        notes=notes,
        source=["manual"],
        verified=True,
    )

    existing = dk.load()
    existing.append(provider)
    dk.save(existing)

    print(f"\n✓ '{name}' gespeichert. ({len(existing)} Einträge in data/unchecked/manual.json)")


if __name__ == "__main__":
    main()
