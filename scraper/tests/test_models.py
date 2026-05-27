"""Tests für scraper/models.py"""

import json

from scraper.tools.models import Address, Coordinates, Contact, Provider


def test_provider_to_dict_minimal():
    """Provider mit nur Pflichtfeldern."""
    p = Provider(
        id="test-berlin",
        name="Test Praxis",
        category="dexa",
        address=Address(street="Teststr. 1", postal_code="10115", city="Berlin", country="DE"),
        coordinates=Coordinates(lat=52.52, lng=13.40),
    )
    d = p.to_dict()
    assert d["id"] == "test-berlin"
    assert d["name"] == "Test Praxis"
    assert d["category"] == "dexa"
    assert d["address"]["street"] == "Teststr. 1"
    assert d["coordinates"]["lat"] == 52.52
    # Optionale Felder nicht im Output
    assert "services" not in d
    assert "contact" not in d
    assert "self_payer" not in d
    assert "prices" not in d
    assert "verified" not in d
    assert "notes" not in d
    assert "docs" not in d
    assert "source" not in d


def test_provider_to_dict_with_optionals():
    """Provider mit allen Feldern."""
    p = Provider(
        id="test-berlin",
        name="Test Praxis",
        category="beide",
        address=Address(street="Teststr. 1", postal_code="10115", city="Berlin", country="DE"),
        coordinates=Coordinates(lat=52.52, lng=13.40),
        services=["DEXA", "Bluttest"],
        contact=Contact(phone="+49 30 123", website="https://test.de"),
        self_payer=True,
        prices={"DEXA": "80 €"},
        verified=True,
        notes="Nur mit Termin",
        docs="Annahme basiert auf Website, nicht verifiziert",
        source=["manual", "google_maps"],
    )
    d = p.to_dict()
    assert d["services"] == ["DEXA", "Bluttest"]
    assert d["contact"]["phone"] == "+49 30 123"
    assert d["self_payer"] is True
    assert d["prices"]["DEXA"] == "80 €"
    assert d["verified"] is True
    assert d["notes"] == "Nur mit Termin"
    assert d["docs"] == "Annahme basiert auf Website, nicht verifiziert"
    assert d["source"] == ["manual", "google_maps"]


def test_provider_to_dict_json_serializable():
    """to_dict() Output ist JSON-serialisierbar."""
    p = Provider(
        id="test-berlin",
        name="Test Praxis",
        category="dexa",
        address=Address(street="Teststr. 1", postal_code="10115", city="Berlin", country="DE"),
        coordinates=Coordinates(lat=52.52, lng=13.40),
        services=["DEXA"],
        source=["manual"],
    )
    d = p.to_dict()
    json_str = json.dumps(d)
    assert json_str  # Kein Fehler = serialisierbar
    loaded = json.loads(json_str)
    assert loaded["id"] == "test-berlin"
    assert loaded["source"] == ["manual"]


def test_provider_to_dict_empty_lists():
    """Leere Listen/Dicts werden weggelassen."""
    p = Provider(
        id="test-berlin",
        name="Test Praxis",
        category="dexa",
        address=Address(street="Teststr. 1", postal_code="10115", city="Berlin", country="DE"),
        coordinates=Coordinates(lat=52.52, lng=13.40),
        services=[],
        prices={},
        source=[],
    )
    d = p.to_dict()
    assert "services" not in d
    assert "prices" not in d
    assert "source" not in d
