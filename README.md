# DEXA & Blutlabor Karte

Interaktive Web-Karte fuer Labore und Praxen, die DEXA Body Composition Scans oder Blutuntersuchungen als Selbstzahler anbieten. Fokus Deutschland.

**280 DE-Eintraege** — 263 Blutlabore, 17 DEXA-Anbieter.

## Quick Start

```bash
# Docker
docker build -t dexa-karte .
docker run -p 8000:8000 dexa-karte
# → http://localhost:8000

# Lokal
python -m venv .venv && source .venv/bin/activate
pip install -r scraper/requirements.txt
python -m scraper.tools.clean --country=DE
python serve.py
```

## Daten-Pipeline

`scraper/tools/clean.py` ist eine 4-Phasen-Pipeline, die Rohdaten aus `data/unchecked/` aufbereitet:

| Phase | Schritt | Beschreibung |
|-------|---------|-------------|
| 1 | Schema-Validierung | `jsonschema` gegen `data/schema.json` |
| 1b | Geocoding | `(0,0)`-Koordinaten via Nominatim nachschlagen |
| 1a | Laenderfilter | Nur `address.country == "DE"` (konfigurierbar via `--country=DE,AT,CH`) |
| 2 | Qualitaetssicherung | Mistral Large beurteilt Datenqualitaet, Website-Erreichbarkeit wird vorab geprueft |
| 4 | Smart-Dedup | Adress-Hash + Website-Domain + Namensaehnlichkeit (>75%) erkennen und mergen |

Ausgabe: `data/providers.json`.

## Scraper

Vier Scraper im Einsatz. Details zu jedem in [SCRAPING.md](SCRAPING.md).

| Scraper | Quelle | Typ | Ausgabe |
|---------|--------|-----|---------|
| `aeon` | aeon.life CMS (Nuxt/Storyblok) | Klassisches Scraping (BS4) | 8 DEXA-Standorte (DE) |
| `blutlabor_opencode_search` | Brave Search + opencode Agent | KI-gestuetzte Suche | 260+ Blutlabore |
| `dexa_opencode_search` | Brave Search + opencode Agent | KI-gestuetzte Suche | 10+ DEXA-Praxen |
| `manual` | Manuelle CLI-Eingabe | Interaktiv | Verifizierte Einzeleintraege |

## Frontend

`web/` — Leaflet.js + Vanilla JS, keine Build-Tools, keine Frameworks. Karte auf Deutschland zentriert, Markerkategorien farblich getrennt, Filterbuttons (Alle/DEXA/Blutlabor), Detail-Panel per Klick. Responsive (Desktop + Mobil).

## Projektstruktur

```
.
├── Dockerfile
├── serve.py                     # Dev-Server (http.server)
├── web/                         # Frontend
│   ├── index.html
│   ├── app.js
│   └── style.css
├── data/
│   ├── schema.json              # JSON Schema (versioniert)
│   ├── providers.json           # Finale Daten (versioniert)
│   └── unchecked/               # Rohdaten (gitignored)
└── scraper/
    ├── requirements.txt
    ├── tools/
    │   ├── clean.py             # 4-Phasen-Pipeline
    │   ├── validate.py          # jsonschema-Validierung
    │   ├── geocode.py           # Nominatim-Geocoding
    │   ├── mistral_kit.py       # Mistral-API-Client
    │   ├── brave_kit.py         # Brave Search-Client
    │   ├── request_kit.py       # HTTP (Rate-Limit, Retry)
    │   ├── data_kit.py          # Provider-Factories, I/O
    │   └── opencode_pipeline.py # Search-Pipeline (Brave → KI)
    ├── scrapers/
    │   ├── aeon/
    │   ├── blutlabor_opencode_search/
    │   ├── dexa_opencode_search/
    │   └── manual/
    └── tests/
```

## Architekturentscheidungen

- **JSON statt DB**: 300 Datensaetze brauchen keine Datenbank. JSON ist git-freundlich, deploymentsfrei. Validierung per `jsonschema`.
- **Leaflet + Vanilla JS**: Kein Build-Tool, keine Runtime-Dependencies. OpenStreetMap-Tiles sind kostenlos.
- **DataKit-Pattern**: Jeder Scraper produziert schema-konforme JSON-Eintraege in `data/unchecked/`. Die Clean-Pipeline validiert, geocoded, filtert und dedupliziert zentral.
- **Unchecked vs. Providers**: Rohdaten (`unchecked/`) sind gitignored und koennen von jedem Scraper ueberschrieben werden. `providers.json` ist das veroeffentlichte Endergebnis und wird getrackt.
- **Smart-Dedup**: Duplikate werden am Output erkannt (Adress-Hash, Website-Domain), nicht am Scraper-Input. So koennen mehrere Scraper dieselbe Praxis finden, ohne sich gegenseitig zu blockieren.

## Bei mehr Zeit

- AT/CH-Daten ergaenzen
- Leaflet.markercluster bei >300 Markern
- FastAPI-Backend mit Such-API
- Automatisierte Preisextraktion
- CI/CD fuer regelmaessige Scraper-Laeufe
