"""
Dataclasses für DEXA & Blutlabor Provider-Einträge.

Jeder Scraper sollte diese Klassen nutzen, um valide Einträge zu erzeugen.
Die to_dict()-Methode liefert ein JSON-serialisierbares dict, das zum Schema passt.

Für konsistente Service-Strings: from scraper.tools.services import Service
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Address:
    """Adresse eines Anbieters."""

    street: str
    postal_code: str
    city: str
    country: str  # "DE", "AT", "CH"


@dataclass
class Coordinates:
    """Geokoordinaten eines Anbieters."""

    lat: float
    lng: float


@dataclass
class Contact:
    """Kontaktdaten eines Anbieters."""

    phone: str | None = None
    website: str | None = None
    email: str | None = None


@dataclass
class Provider:
    """
    Ein Anbieter für DEXA-Scans oder Blutuntersuchungen.

    Alle Felder entsprechen dem Schema in data/schema.json.
    Optionale Felder sind None per Default und werden in to_dict() weggelassen.
    """

    id: str
    name: str
    category: str  # "dexa", "blutlabor", "beide"
    address: Address
    coordinates: Coordinates
    services: list[str] = field(default_factory=list)  # Service-Enum-Werte verwenden
    contact: Contact | None = None
    self_payer: bool | None = None
    prices: dict[str, str] = field(default_factory=dict)
    verified: bool | None = None
    notes: str | None = None
    docs: str | None = None
    source: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """
        Konvertiert das Provider-Objekt in ein dict.

        - Nested Dataclasses werden rekursiv in dicts umgewandelt
        - Felder mit Wert None, leere Listen oder leere Dicts werden weggelassen
        - Booleans (auch False) werden behalten
        """
        d = _asdict_recursive(self)
        return {
            k: v for k, v in d.items()
            if not (v is None or v == [] or v == {})
        }


def _asdict_recursive(obj: Any) -> dict[str, Any]:
    """Rekursives asdict für nested Dataclasses."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _asdict_recursive(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_asdict_recursive(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _asdict_recursive(v) for k, v in obj.items()}
    return obj
