"""Tests für scraper/clean.py"""

import json
import tempfile
from pathlib import Path

import pytest

from scraper.clean import clean, deduplicate, load_unchecked_entries, merge_sources


def test_load_unchecked_entries_empty_dir():
    """Leeres unchecked-Verzeichnis liefert leere Liste."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Simuliere leeres unchecked-Verzeichnis
        unchecked_dir = Path(tmpdir) / "unchecked"
        unchecked_dir.mkdir()
        # Patch DATA_DIR für den Test
        import scraper.clean as clean_module
        original = clean_module.UNCHECKED_DIR
        clean_module.UNCHECKED_DIR = unchecked_dir
        try:
            entries = load_unchecked_entries()
            assert entries == []
        finally:
            clean_module.UNCHECKED_DIR = original


def test_load_unchecked_entries_multiple_files():
    """Lädt Einträge aus mehreren JSON-Dateien."""
    with tempfile.TemporaryDirectory() as tmpdir:
        unchecked_dir = Path(tmpdir) / "unchecked"
        unchecked_dir.mkdir()

        # Schreibe Test-Dateien
        file1 = unchecked_dir / "a.json"
        file1.write_text(json.dumps([{"id": "a1"}, {"id": "a2"}]))
        file2 = unchecked_dir / "b.json"
        file2.write_text(json.dumps([{"id": "b1"}]))

        import scraper.clean as clean_module
        original = clean_module.UNCHECKED_DIR
        clean_module.UNCHECKED_DIR = unchecked_dir
        try:
            entries = load_unchecked_entries()
            assert len(entries) == 3
            ids = {e["id"] for e in entries}
            assert ids == {"a1", "a2", "b1"}
        finally:
            clean_module.UNCHECKED_DIR = original


def test_deduplicate_same_id():
    """Dedupliziert Einträge mit gleicher id."""
    entries = [
        {"id": "same", "name": "First", "source": ["a"]},
        {"id": "same", "name": "Second", "source": ["b"]},
        {"id": "other", "name": "Other", "source": ["c"]},
    ]
    deduped = deduplicate(entries)
    assert len(deduped) == 2
    assert "same" in deduped
    assert "other" in deduped
    # source-Arrays gemerged
    assert sorted(deduped["same"]["source"]) == ["a", "b"]
    # Erster Eintrag gewinnt (name = "First")
    assert deduped["same"]["name"] == "First"


def test_deduplicate_no_dupes():
    """Keine Duplikate = alle bleiben."""
    entries = [
        {"id": "a", "name": "A"},
        {"id": "b", "name": "B"},
    ]
    deduped = deduplicate(entries)
    assert len(deduped) == 2


def test_merge_sources():
    """Konvertiert deduped dict zurück in Liste."""
    deduped = {
        "a": {"id": "a", "name": "A"},
        "b": {"id": "b", "name": "B"},
    }
    merged = merge_sources(deduped)
    assert len(merged) == 2
    assert all(isinstance(e, dict) for e in merged)


def test_clean_integration(tmp_path):
    """Integrationstest: clean() mit temporärem data-Verzeichnis."""
    # Erstelle temporäre Struktur
    data_dir = tmp_path / "data"
    unchecked_dir = data_dir / "unchecked"
    unchecked_dir.mkdir(parents=True)

    # Schreibe Test-Daten
    (unchecked_dir / "a.json").write_text(
        json.dumps([
            {
                "id": "valid1",
                "name": "Valid 1",
                "category": "dexa",
                "address": {"street": "s", "postal_code": "p", "city": "c", "country": "DE"},
                "coordinates": {"lat": 0, "lng": 0},
                "source": ["a"],
            },
            {
                "id": "valid2",
                "name": "Valid 2",
                "category": "blutlabor",
                "address": {"street": "s", "postal_code": "p", "city": "c", "country": "DE"},
                "coordinates": {"lat": 0, "lng": 0},
                "source": ["a"],
            },
        ])
    )
    (unchecked_dir / "b.json").write_text(
        json.dumps([
            {
                "id": "valid1",  # Duplikat
                "name": "Valid 1 Dup",
                "category": "dexa",
                "address": {"street": "s", "postal_code": "p", "city": "c", "country": "DE"},
                "coordinates": {"lat": 0, "lng": 0},
                "source": ["b"],
            },
            {"id": "invalid", "name": "Invalid"},  # Fehlende Pflichtfelder
        ])
    )

    # Patch DATA_DIR für den Test
    import scraper.clean as clean_module
    original_data = clean_module.DATA_DIR
    original_unchecked = clean_module.UNCHECKED_DIR
    original_output = clean_module.OUTPUT_FILE
    clean_module.DATA_DIR = data_dir
    clean_module.UNCHECKED_DIR = unchecked_dir
    clean_module.OUTPUT_FILE = data_dir / "providers.json"

    try:
        merged, errors = clean_module.clean()

        # 1 gültiger Eintrag (valid2) + 1 deduplizierter (valid1)
        assert len(merged) == 2
        ids = {e["id"] for e in merged}
        assert ids == {"valid1", "valid2"}

        # valid1 hat gemergte sources
        valid1 = next(e for e in merged if e["id"] == "valid1")
        assert sorted(valid1["source"]) == ["a", "b"]
        assert valid1["name"] == "Valid 1"  # Erster Eintrag gewinnt

        # 1 Fehler (invalid Eintrag)
        assert len(errors) > 0

        # Output-Datei manuell schreiben und prüfen
        output_file = data_dir / "providers.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
        assert output_file.exists()

    finally:
        clean_module.DATA_DIR = original_data
        clean_module.UNCHECKED_DIR = original_unchecked
        clean_module.OUTPUT_FILE = original_output
