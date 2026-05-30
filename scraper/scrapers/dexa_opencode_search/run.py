"""DEXA Brave Search + opencode Agent Pipeline.

Usage:
    python -m scraper.scrapers.dexa_opencode_search.run
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scraper.tools.opencode_pipeline import PipelineConfig, run_search_pipeline

QUERIES = [
    # Consumer / Fitness-Kontext
    "DEXA Koerperfettmessung",
    "DEXA Ganzkoerper Scan",
    # Radiologie / klinisch — Praxen die DXA haben aber nicht als "Körperfettmessung" vermarkten
    "DXA Ganzkoerperanalyse",
    # Klinik / Krankenhaus — Endokrinologie, Adipositas-Zentren, Unikliniken
    "DXA Koerperzusammensetzung",
    # Sportmedizin / Leistungsdiagnostik
    "DXA Sportmedizin Koerperfett",
]

OPENACODE_PROMPT = """Du bist ein spezialisierter Web-Scraping-Agent fuer DEXA-Koerperfettmessung.

AUFGABE: Besuche {url} und pruefe, ob dort DEXA-GANZKOERPER-KOERPERFETTMESSUNG angeboten wird.

WARNUNG: Die meisten DEXA-Anbieter machen NUR Knochendichtemessung (Osteoporose-Diagnostik).
Das zaehlt NICHT! Wir suchen AUSSCHLIESSLICH Anbieter die zusaetzlich KOERPERFETTANALYSE machen.

ACHTUNG: Nur weil in einem Text allgemein erklaert wird, dass ein DXA-Geraet theoretisch auch Koerperzusammensetzung messen kann, reicht das NICHT aus! Die Praxis muss den Ganzkoerper-Scan als konkretes, fuer Patienten buchbares Leistungsangebot anpreisen oder in einer Preis- bzw. Leistungsliste fuehren.

SCHRITTE:
1. Lade die Startseite mit WebFetch.
2. SUCHE SYSTEMATISCH NACH UNTERSEITEN — die Info ob Ganzkoerper-Scans angeboten werden steht oft NICHT auf der Startseite, sondern auf Unterseiten! Pruefe insbesondere:
   - Navigations-Links wie "Leistungen", "Diagnostik", "DEXA", "DXA", "Knochendichte", "Osteoporose", "Vorsorge", "Preise"
   - Links die "Koerperfett", "Body Composition", "Ganzkoerper", "Koerperzusammensetzung", "Adipositas" im Text haben
   - Bei Kliniken/Krankenhaeusern: auch Seiten der Endokrinologie, Sportmedizin, Radiologie aufrufen
3. Rufe alle vielversprechenden Unterseiten auf und lies sie gruendlich.
4. PRUEFE ZWEI DINGE:
   A) Bietet die Einrichtung ueberhaupt DEXA/DXA an?
   B) Bietet sie SPEZIFISCH Ganzkoerper-Koerperfettanalyse / Body Composition als BUCHBARE LEISTUNG an?
      (Reine Knochendichtemessung ohne Koerperfett = NICHT relevant!
       Beilaeufige allgemeine Erlaeuterung der Geraetefunktion = NICHT relevant!)
5. Extrahiere Adress- und Kontaktdaten, Preise falls vorhanden.

BEISPIELE:
- "DEXA-Knochendichtemessung" -> NICHT relevant (nur Knochen)
- "DEXA Body Composition / Koerperfettmessung" -> RELEVANT
- "Ganzkoerper-DEXA-Scan mit Koerperfettanalyse" -> RELEVANT
- "Osteodensitometrie / Osteoporose-Diagnostik" -> NICHT relevant

WICHTIG: Deine finale Ausgabe MUSS NUR diesen exakten JSON-Block enthalten. NICHTS anderes.

```json
{{
  "is_target": true,
  "name": "Praxis- oder Zentrumsname",
  "street": "Strasse und Hausnummer",
  "postal_code": "12345",
  "city": "Stadt",
  "country": "DE",
  "phone": "Telefonnummer",
  "email": "E-Mail oder null",
  "website": "{url}",
  "prices": {{"DEXA Body Composition": "85 EUR"}},
  "has_body_composition": true
}}
```

Wenn die Einrichtung KEINE DEXA-Ganzkoerper-Koerperfettmessung anbietet:
```json
{{
  "is_target": false,
  "reason": "nur Knochendichtemessung, keine Koerperfettanalyse"
}}
```"""

config = PipelineConfig(
    name="dexa_search",
    category="dexa",
    service="DEXA Body Composition",
    queries=QUERIES,
    prompt_template=OPENACODE_PROMPT,
    id_prefix="dexa-",
    extra_validate=lambda r: r.get("has_body_composition", True),
    include_prices=True,
    self_payer_from=True,
)


def main() -> None:
    run_search_pipeline(config)


if __name__ == "__main__":
    main()
