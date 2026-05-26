"""
Kit — einheitliches Interface für alle Scraper-Skripte.

Bündelt Models, Service-Enum und Datei-I/O in einem Objekt.
Jeder Scraper initialisiert ein Kit mit seinem Namen und kann
darüber Provider erstellen, speichern und laden.
"""

import json
from pathlib import Path

from scraper.tools.models import Address, Contact, Coordinates, Provider
from scraper.tools.services import Service

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
UNCHECKED_DIR = DATA_DIR / "unchecked"


class Kit:
    """
    Scraper-Werkzeugkasten.

    Usage:
        kit = Kit("overpass_de")
        p = kit.provider(
            id="praxis-hannover",
            name="Praxis Hannover",
            category="dexa",
            address=kit.address(street="...", postal_code="...", city="Hannover", country="DE"),
            coordinates=kit.coordinates(lat=52.37, lng=9.73),
            services=[kit.svc.DEXA_BODY_COMP],
        )
        kit.save([p])
    """

    def __init__(self, name: str):
        """
        Args:
            name: Name des Scrapers (z.B. "overpass_de", "google_hannover").
                  Wird als Dateiname in data/unchecked/ verwendet.
        """
        self.name = name

    # ---- Models (Factory-Shortcuts) ----

    @staticmethod
    def provider(
        id: str,
        name: str,
        category: str,
        address: Address,
        coordinates: Coordinates,
        services: list[str] | None = None,
        contact: Contact | None = None,
        self_payer: bool | None = None,
        prices: dict[str, str] | None = None,
        verified: bool | None = None,
        notes: str | None = None,
        source: list[str] | None = None,
    ) -> Provider:
        return Provider(
            id=id,
            name=name,
            category=category,
            address=address,
            coordinates=coordinates,
            services=services or [],
            contact=contact,
            self_payer=self_payer,
            prices=prices or {},
            verified=verified,
            notes=notes,
            source=source or [],
        )

    @staticmethod
    def address(street: str, postal_code: str, city: str, country: str) -> Address:
        return Address(street=street, postal_code=postal_code, city=city, country=country)

    @staticmethod
    def coordinates(lat: float, lng: float) -> Coordinates:
        return Coordinates(lat=lat, lng=lng)

    @staticmethod
    def contact(phone: str | None = None, website: str | None = None, email: str | None = None) -> Contact:
        return Contact(phone=phone, website=website, email=email)

    # ---- Service Enum ----

    @property
    def svc(self) -> type[Service]:
        """Service Enum für type-safe Leistungs-Strings."""
        return Service

    # ---- Datei-I/O ----

    @property
    def _output_path(self) -> Path:
        UNCHECKED_DIR.mkdir(parents=True, exist_ok=True)
        return UNCHECKED_DIR / f"{self.name}.json"

    def save(self, providers: list[Provider]) -> None:
        """
        Schreibt Providers nach data/unchecked/<name>.json.
        Überschreibt die Datei komplett.
        """
        entries = [p.to_dict() for p in providers]
        with open(self._output_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    def load(self) -> list[Provider]:
        """
        Lädt vorhandene Einträge aus data/unchecked/<name>.json.
        Gibt leere Liste zurück, wenn die Datei nicht existiert.
        """
        if not self._output_path.exists():
            return []
        with open(self._output_path, encoding="utf-8") as f:
            entries = json.load(f)

        providers = []
        for e in entries:
            providers.append(Provider(
                id=e["id"],
                name=e["name"],
                category=e["category"],
                address=Address(**e["address"]),
                coordinates=Coordinates(**e["coordinates"]),
                services=e.get("services", []),
                contact=Contact(**e["contact"]) if e.get("contact") else None,
                self_payer=e.get("self_payer"),
                prices=e.get("prices", {}),
                verified=e.get("verified"),
                notes=e.get("notes"),
                source=e.get("source", []),
            ))
        return providers
