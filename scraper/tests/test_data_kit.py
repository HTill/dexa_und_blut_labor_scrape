"""Tests für scraper/tools/data_kit.py"""

import json
from pathlib import Path

from scraper.tools.data_kit import DataKit
from scraper.tools.models import Address, Coordinates
from scraper.tools.services import Service


def test_datakit_save_and_load(tmp_path):
    """DataKit kann Providers speichern und laden."""
    import scraper.tools.data_kit as dk_module
    original = dk_module.UNCHECKED_DIR
    dk_module.UNCHECKED_DIR = tmp_path / "unchecked"

    try:
        dk = DataKit("test_scraper")

        provider = dk.provider(
            id="test-hannover",
            name="Test Praxis Hannover",
            category="dexa",
            address=dk.address(street="Str 1", postal_code="30159", city="Hannover", country="DE"),
            coordinates=dk.coordinates(lat=52.37, lng=9.73),
            services=[dk.svc.DEXA_BODY_COMP],
            source=["test"],
            verified=True,
        )

        dk.save([provider])

        output = tmp_path / "unchecked" / "test_scraper.json"
        assert output.exists()

        loaded = dk.load()
        assert len(loaded) == 1
        assert loaded[0].id == "test-hannover"
        assert loaded[0].services == [Service.DEXA_BODY_COMP]
        assert loaded[0].verified is True
    finally:
        dk_module.UNCHECKED_DIR = original


def test_datakit_load_empty():
    """DataKit.load() gibt leere Liste zurück wenn keine Datei existiert."""
    import scraper.tools.data_kit as dk_module
    original = dk_module.UNCHECKED_DIR
    dk_module.UNCHECKED_DIR = Path("/tmp/nonexistent_dk_test")

    try:
        dk = DataKit("nonexistent")
        assert dk.load() == []
    finally:
        dk_module.UNCHECKED_DIR = original


def test_datakit_svc_property():
    """svc property gibt Service Enum zurück."""
    dk = DataKit("test")
    assert dk.svc.DEXA_BODY_COMP == Service.DEXA_BODY_COMP
    assert dk.svc.BLOOD_SELF_PAYER == Service.BLOOD_SELF_PAYER


def test_datakit_factory_methods():
    """Factory-Methoden erstellen die richtigen Typen."""
    dk = DataKit("test")

    addr = dk.address(street="s", postal_code="p", city="c", country="DE")
    assert isinstance(addr, Address)
    assert addr.street == "s"

    coords = dk.coordinates(lat=52.0, lng=9.0)
    assert isinstance(coords, Coordinates)
    assert coords.lat == 52.0

    contact = dk.contact(phone="+49 123")
    assert contact.phone == "+49 123"
    assert contact.website is None


def test_datakit_provider_minimal():
    """dk.provider() mit nur Pflichtfeldern."""
    dk = DataKit("test")
    p = dk.provider(
        id="minimal",
        name="Minimal",
        category="blutlabor",
        address=dk.address(street="s", postal_code="p", city="c", country="DE"),
        coordinates=dk.coordinates(lat=0, lng=0),
    )
    assert p.id == "minimal"
    assert p.category == "blutlabor"
    assert p.services == []
    assert p.verified is None
