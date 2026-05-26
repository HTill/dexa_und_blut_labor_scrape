"""
Clean-Script: aggregiert alle unchecked/*.json, dedupliziert per id,
validiert gegen Schema und schreibt providers.json.
"""

import json
import sys
from pathlib import Path

from scraper.validate import validate_entry

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UNCHECKED_DIR = DATA_DIR / "unchecked"
OUTPUT_FILE = DATA_DIR / "providers.json"


def load_unchecked_entries() -> list[dict]:
    """Lädt alle Einträge aus data/unchecked/*.json."""
    if not UNCHECKED_DIR.exists():
        return []

    entries = []
    for filepath in sorted(UNCHECKED_DIR.glob("*.json")):
        with open(filepath, encoding="utf-8") as f:
            entries.extend(json.load(f))
    return entries


def deduplicate(entries: list[dict]) -> dict[str, dict]:
    """
    Dedupliziert Einträge per id-Feld.

    Bei Duplikaten:
    - source-Arrays werden gemerged
    - Alle anderen Felder: erster Eintrag gewinnt

    Returns:
        dict mit id als Key und gemergtem Eintrag als Value
    """
    seen: dict[str, dict] = {}
    for entry in entries:
        entry_id = entry["id"]
        if entry_id not in seen:
            seen[entry_id] = entry
        else:
            # Merge source arrays
            existing_sources = set(seen[entry_id].get("source", []))
            new_sources = set(entry.get("source", []))
            seen[entry_id]["source"] = sorted(existing_sources | new_sources)
    return seen


def merge_sources(deduped: dict[str, dict]) -> list[dict]:
    """Konvertiert deduped dict zurück in Liste."""
    return list(deduped.values())


def clean() -> tuple[list[dict], list[str]]:
    """
    Hauptfunktion: lädt, validiert, dedupliziert, sortiert.

    Returns:
        Tuple aus (gültige Einträge, Liste aller Fehler)
    """
    raw_entries = load_unchecked_entries()
    all_errors: list[str] = []
    valid_entries: list[dict] = []

    # Validieren
    for i, entry in enumerate(raw_entries):
        errors = validate_entry(entry)
        if errors:
            all_errors.extend(f"[Eintrag {i} - {entry.get('id', 'unknown')}] {e}" for e in errors)
        else:
            valid_entries.append(entry)

    # Deduplizieren
    deduped = deduplicate(valid_entries)
    merged = merge_sources(deduped)

    # Sortieren nach name
    merged.sort(key=lambda x: x.get("name", "").lower())

    return merged, all_errors


def main() -> None:
    """CLI-Einstieg: clean.py ohne Argumente ausführen."""
    merged, errors = clean()

    # Fehler ausgeben
    if errors:
        print(f"⚠ {len(errors)} Validierungsfehler:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)

    # Schreiben
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"✓ {len(merged)} Einträge nach data/providers.json geschrieben")


if __name__ == "__main__":
    main()
