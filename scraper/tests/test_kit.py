"""Tests für scraper/tools/kit.py"""

import json
import tempfile
from pathlib import Path

from scraper.tools.kit import Kit
from scraper.tools.models import Address, Coordinates
from scraper.tools.services import Service


def test_kit_save_and_load(tmp_path):
    """Kit kann Providers speichern und laden."""
    import scraper.tools.kit as kit_module
    original = kit_module.UNCHECKED_DIR
    kit_module.UNCHECKED_DIR = tmp_path / "unchecked"

    try:
        kit = Kit("test_scraper")

        provider = kit.provider(
            id="test-hannover",
            name="Test Praxis Hannover",
            category="dexa",
            address=kit.address(street="Str 1", postal_code="30159", city="Hannover", country="DE"),
            coordinates=kit.coordinates(lat=52.37, lng=9.73),
            services=[kit.svc.DEXA_BODY_COMP],
            source=["test"],
            verified=True,
        )

        kit.save([provider])

        # Datei wurde geschrieben
        output = tmp_path / "unchecked" / "test_scraper.json"
        assert output.exists()

        # Inhalt ist valides JSON mit unserem Eintrag
        loaded = kit.load()
        assert len(loaded) == 1
        assert loaded[0].id == "test-hannover"
        assert loaded[0].name == "Test Praxis Hannover"
        assert loaded[0].services == [Service.DEXA_BODY_COMP]
        assert loaded[0].verified is True
    finally:
        kit_module.UNCHECKED_DIR = original


def test_kit_load_empty():
    """Kit.load() gibt leere Liste zurück wenn keine Datei existiert."""
    import scraper.tools.kit as kit_module
    original = kit_module.UNCHECKED_DIR
    kit_module.UNCHECKED_DIR = Path("/tmp/nonexistent_kit_test")

    try:
        kit = Kit("nonexistent")
        assert kit.load() == []
    finally:
        kit_module.UNCHECKED_DIR = original


def test_kit_svc_property():
    """svc property gibt Service Enum zurück."""
    kit = Kit("test")
    assert kit.svc.DEXA_BODY_COMP == Service.DEXA_BODY_COMP
    assert kit.svc.BLOOD_SELF_PAYER == Service.BLOOD_SELF_PAYER
    assert kit.svc.DEXA_BONE_DENSITY == Service.DEXA_BONE_DENSITY


def test_kit_factory_methods():
    """Factory-Methoden erstellen die richtigen Typen."""
    kit = Kit("test")

    addr = kit.address(street="s", postal_code="p", city="c", country="DE")
    assert isinstance(addr, Address)
    assert addr.street == "s"
    assert addr.country == "DE"

    coords = kit.coordinates(lat=52.0, lng=9.0)
    assert isinstance(coords, Coordinates)
    assert coords.lat == 52.0
    assert coords.lng == 9.0

    contact = kit.contact(phone="+49 123")
    assert contact.phone == "+49 123"
    assert contact.website is None
    assert contact.email is None


def test_kit_provider_minimal():
    """kit.provider() mit nur Pflichtfeldern."""
    kit = Kit("test")
    p = kit.provider(
        id="minimal",
        name="Minimal",
        category="blutlabor",
        address=kit.address(street="s", postal_code="p", city="c", country="DE"),
        coordinates=kit.coordinates(lat=0, lng=0),
    )
    assert p.id == "minimal"
    assert p.category == "blutlabor"
    assert p.services == []
    assert p.source == []
    assert p.verified is None
