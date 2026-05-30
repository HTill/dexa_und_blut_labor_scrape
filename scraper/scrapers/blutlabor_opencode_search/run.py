"""Blutlabor Brave Search + opencode Agent Pipeline.

Usage:
    python -m scraper.scrapers.blutlabor_opencode_search.run
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scraper.tools.opencode_pipeline import PipelineConfig, run_search_pipeline

QUERIES = [
    "IGeL Leistung Bluttests",
    "Blutwerte testen lassen privat",
]

OPENACODE_PROMPT = """Du bist ein spezialisierter Web-Scraping-Agent fuer Blutlabore.

AUFGABE: Besuche {url} und pruefe, ob dort Bluttests fuer SELBSTZAHLER / PRIVATPATIENTEN angeboten werden.

SCHRITTE:
1. Lade die Website mit deinen Tools.
2. Lies die Startseite und navigiere zu Unterseiten wie "Leistungen", "Labor", "Diagnostik",
   "IGeL", "Selbstzahler", "Privatpatient", "Preise" oder "Kosten".
3. Pruefe KRITISCH: Bietet diese Einrichtung Bluttests fuer Selbstzahler an?
   - JA: Direktlabor, IGeL-Labor, privat zugaengliches Labor mit Blutentnahme
   - NEIN: Blutspendedienst (Haema, DRK), reine Kassenarztpraxis, Apotheke, Fitnessstudio
4. Extrahiere Adress- und Kontaktdaten.

WICHTIG: Deine finale Ausgabe MUSS NUR diesen exakten JSON-Block enthalten. NICHTS anderes.
KEIN Markdown ausserhalb des Codeblocks. KEINE Erklaerungen.

```json
{{
  "is_target": true,
  "name": "Praxis- oder Laborname",
  "street": "Strasse und Hausnummer",
  "postal_code": "12345",
  "city": "Stadt",
  "country": "DE",
  "phone": "Telefonnummer",
  "email": "E-Mail oder null",
  "website": "{url}",
  "self_payer_confirmed": true
}}
```

Wenn die Einrichtung KEINE Bluttests fuer Selbstzahler anbietet:
```json
{{
  "is_target": false
}}
```"""

config = PipelineConfig(
    name="blutlabor_search",
    category="blutlabor",
    service="Bluttest Selbstzahler",
    queries=QUERIES,
    prompt_template=OPENACODE_PROMPT,
    id_prefix="blut-",
    extra_validate=None,
    include_prices=False,
    self_payer_from="self_payer_confirmed",
)


def main() -> None:
    run_search_pipeline(config)


if __name__ == "__main__":
    main()
