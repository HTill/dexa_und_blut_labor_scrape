"""
Validierung von Provider-Einträgen gegen das JSON Schema.
"""

import json
from pathlib import Path

import jsonschema

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "data" / "schema.json"


def load_schema() -> dict:
    """Lädt das Schema aus data/schema.json."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def validate_entry(entry: dict) -> list[str]:
    """
    Validiert einen einzelnen Provider-Eintrag gegen das Schema.

    Args:
        entry: Ein dict, das einem Provider entspricht

    Returns:
        Liste von Fehler-Nachrichten. Leere Liste = gültig.
    """
    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for error in validator.iter_errors(entry):
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
        errors.append(f"{path}: {error.message}")
    return errors


def validate_file(filepath: Path) -> tuple[list[dict], list[str]]:
    """
    Validiert eine JSON-Datei mit Provider-Einträgen.

    Args:
        filepath: Pfad zur JSON-Datei

    Returns:
        Tuple aus (gültige Einträge, Liste aller Fehler)
    """
    with open(filepath, encoding="utf-8") as f:
        entries = json.load(f)

    valid_entries = []
    all_errors = []

    for i, entry in enumerate(entries):
        errors = validate_entry(entry)
        if errors:
            all_errors.extend(f"[Eintrag {i}] {e}" for e in errors)
        else:
            valid_entries.append(entry)

    return valid_entries, all_errors
