"""Tests für scraper/validate.py"""

import json
import tempfile
from pathlib import Path

import pytest

from scraper.tools.validate import load_schema, validate_entry, validate_file


def test_load_schema():
    """Schema kann geladen werden."""
    schema = load_schema()
    assert "properties" in schema
    assert "id" in schema["properties"]
    assert "source" in schema["properties"]


def test_validate_entry_valid():
    """Valider Eintrag hat keine Fehler."""
    entry = {
        "id": "test-berlin",
        "name": "Test Praxis",
        "category": "dexa",
        "address": {
            "street": "Teststr. 1",
            "postal_code": "10115",
            "city": "Berlin",
            "country": "DE",
        },
        "coordinates": {"lat": 52.52, "lng": 13.40},
    }
    errors = validate_entry(entry)
    assert errors == []


def test_validate_entry_missing_required():
    """Fehlende Pflichtfelder werden erkannt."""
    entry = {"id": "test"}
    errors = validate_entry(entry)
    assert len(errors) > 0
    assert any("name" in e for e in errors)
    assert any("category" in e for e in errors)
    assert any("address" in e for e in errors)
    assert any("coordinates" in e for e in errors)


def test_validate_entry_invalid_category():
    """Ungültige Kategorie wird erkannt."""
    entry = {
        "id": "test",
        "name": "Test",
        "category": "invalid",
        "address": {"street": "s", "postal_code": "p", "city": "c", "country": "DE"},
        "coordinates": {"lat": 0, "lng": 0},
    }
    errors = validate_entry(entry)
    assert len(errors) > 0
    assert any("category" in e for e in errors)


def test_validate_entry_valid_with_docs():
    """Eintrag mit docs-Feld ist valide."""
    entry = {
        "id": "test",
        "name": "Test",
        "category": "dexa",
        "address": {"street": "s", "postal_code": "p", "city": "c", "country": "DE"},
        "coordinates": {"lat": 0, "lng": 0},
        "docs": "Annahme: Alle Labore bieten Selbstzahler an, nicht verifiziert",
    }
    errors = validate_entry(entry)
    assert errors == []


def test_validate_entry_valid_with_source():
    """Eintrag mit source-Array ist valide."""
    entry = {
        "id": "test",
        "name": "Test",
        "category": "dexa",
        "address": {"street": "s", "postal_code": "p", "city": "c", "country": "DE"},
        "coordinates": {"lat": 0, "lng": 0},
        "source": ["manual", "google"],
    }
    errors = validate_entry(entry)
    assert errors == []


def test_validate_file():
    """Validiert eine JSON-Datei."""
    entries = [
        {
            "id": "valid",
            "name": "Valid",
            "category": "dexa",
            "address": {"street": "s", "postal_code": "p", "city": "c", "country": "DE"},
            "coordinates": {"lat": 0, "lng": 0},
        },
        {"id": "invalid"},  # Missing required fields
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(entries, f)
        f.flush()
        filepath = Path(f.name)

    try:
        valid, errors = validate_file(filepath)
        assert len(valid) == 1
        assert valid[0]["id"] == "valid"
        assert len(errors) > 0
        assert any("Eintrag 1" in e for e in errors)
    finally:
        filepath.unlink()
