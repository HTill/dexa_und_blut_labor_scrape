# DEXA & Blutlabor Scrape — Interaktive Karte DACH

Webanwendung zur Suche von DEXA Body Composition Scans und Blutlaboren (Selbstzahler) in Deutschland, Österreich und der Schweiz.

## Setup

```bash
git clone git@github.com:HTill/dexa_und_blut_labor_scrape.git
cd dexa_und_blut_labor_scrape

# Python-Venv aufsetzen
python -m venv .venv
source .venv/bin/activate
pip install -r scraper/requirements.txt

# Tests
python -m pytest scraper/tests/

# Daten erfassen (interaktiv)
python -m scraper.scrapers.manual.run

# Daten mergen
python -m scraper.tools.clean

# Web-Karte starten
open web/index.html
# oder:
python -m http.server 8000 --directory web
```

## Struktur

```
├── README.md
├── SCRAPING.md                # Scraping-Dokumentation & Sessions
├── BEWERBUNGSAUFGABE.md       # Original-Aufgabenstellung
├── data/
│   └── schema.json            # JSON Schema (versioniert)
├── scraper/
│   ├── tools/                 # Helfer
│   │   ├── models.py          # Provider-Dataclass
│   │   ├── services.py        # Service Enum
│   │   ├── data_kit.py        # Provider-Factories + Datei-I/O
│   │   ├── request_kit.py     # HTTP mit Proxy, Rate-Limit, Retry
│   │   ├── validate.py        # jsonschema-Validierung
│   │   └── clean.py           # unchecked → providers.json (dedup)
│   ├── scrapers/              # Jeder Scraper in eigenem Ordner
│   │   └── manual/run.py      # Interaktiver CLI-Scraper
│   ├── tests/                 # 31 Tests (pytest)
│   └── requirements.txt
└── web/
    ├── index.html             # Kartenansicht
    ├── app.js                 # Leaflet-Logik
    └── style.css
```

`data/unchecked/` und `data/providers.json` sind in `.gitignore` — nur `schema.json` ist versioniert.

## Workflow

1. **Daten erfassen:** `python -m scraper.scrapers.manual.run` → schreibt `data/unchecked/manual.json`
2. **Daten mergen:** `python -m scraper.tools.clean` → validiert, dedupliziert, schreibt `data/providers.json`
3. **Karte starten:** `open web/index.html` → lädt `data/providers.json`

## Entscheidungen

- **Leaflet.js** für die Karte: leichtgewichtig, kein Build-Tool nötig, OpenStreetMap-Tiles kostenlos.
- **JSON** als Datenformat: maschinenlesbar, einfach erweiterbar, ohne Datenbank-Setup.
- **Python** für Scraping: Requests + BeautifulSoup, jsonschema-Validierung.
- **DataKit/RequestKit** getrennt: Provider-Erstellung und HTTP-Requests sind unabhängige Concerns.
- **unchecked-Verzeichnis:** Rohdaten werden von `clean.py` validiert und dedupliziert, bevor sie auf die Karte kommen.
- **Service Enum:** Type-safe Leistungs-Strings, einfach erweiterbar.
- **Kein Framework-Overhead**: Vanilla JS + Leaflet reicht für die Aufgabe.

## Bei mehr Zeit

- Google Maps Places API / Firecrawl / Apify als weitere Scraper
- GeoJSON statt Flat-JSON für direkte Leaflet-Kompatibilität
- Clustering bei vielen Markern (Leaflet.markercluster)
- Backend mit FastAPI + SQLite für Filter/Suche
- Docker-Compose für Ein-Klick-Start
- Automatisiertes Geocoding per Nominatim-API
- nginx-Proxy-Setup für IP-Rotation bei API-Scraping
