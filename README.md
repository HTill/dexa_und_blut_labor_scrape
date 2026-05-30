# DEXA & Blutlabor Karte — DACH

Interaktive Web-Karte für Labore und Praxen im DACH-Raum, die **DEXA Body Composition Scans** oder **Blutuntersuchungen als Selbstzahler** anbieten.

- **280 DE-Anbieter** (263 Blutlabore + 17 DEXA)
- **Verifizierte Daten** mit Website-Checks und Mistral-Qualitaetspruefung
- **Deduplizierung** per ID und aehnlicher Adressen/Namen
- **Geocoding** aller Adressen via Nominatim

## Quick Start (Docker)

```bash
docker build -t dexa-karte .
docker run -p 8000:8000 dexa-karte
# Karte unter http://localhost:8000
```

## Lokale Entwicklung

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r scraper/requirements.txt

# Daten-Pipeline ausfuehren (unchecked/*.json → providers.json)
python -m scraper.tools.clean

# Karte starten
python serve.py
# → http://localhost:8000
```

## Daten-Pipeline

```
                    ┌──────────────┐
                    │ Phase 1       │
     unchecked/*    │ Schema-       │
     ──────────►    │ Validierung   │
                    └──────┬───────┘
                           │ gültige Einträge
                    ┌──────▼───────┐
                    │ Phase 1b     │
                    │ Geocoding    │  (0,0-Koordinaten via Nominatim)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Phase 1a     │
                    │ Länderfilter │  (DE default, --country=DE,AT,CH)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Phase 2      │
                    │ Website-     │  HTTP-Status + Mistral QS
                    │ Check        │  (nur mit API-Key)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Phase 4      │
                    │ Smart-Dedup  │  Gleiche Adresse/Website → Mergen
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ providers    │
                    │ .json        │
                    └──────────────┘
```

## Projektstruktur

```
.
├── Dockerfile                   # Webserver im Container
├── serve.py                     # Lokaler Dev-Server
├── web/                         # Frontend (Leaflet.js + Vanilla JS)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── data/
│   ├── schema.json              # JSON-Schema (versioniert)
│   ├── providers.json           # Finale bereinigte Daten (versioniert)
│   └── unchecked/               # Rohdaten der Scraper (gitignored)
└── scraper/
    ├── requirements.txt
    ├── tools/
    │   ├── clean.py             # 4-Phasen-Pipeline
    │   ├── geocode.py           # Nominatim-Geocoding
    │   ├── validate.py          # jsonschema-Validierung
    │   ├── mistral_kit.py       # Mistral-API-Client
    │   ├── brave_kit.py         # Brave Search API-Client
    │   ├── request_kit.py       # HTTP mit Rate-Limiting + Retry
    │   ├── data_kit.py          # Provider-Factories + I/O
    │   └── opencode_pipeline.py # Generische Suchpipeline
    ├── scrapers/
    │   ├── aeon/                # aeon.life DEXA-Standorte
    │   ├── blutlabor_opencode_search/  # Blutlabor ermittelt via KI
    │   └── dexa_opencode_search/       # DEXA-Anbieter via KI
    └── tests/
```

## Architektur-Entscheidungen

- **Leaflet.js + Vanilla JS**: Kein Build-Tool, keine Framework-Abhaengigkeit, OpenStreetMap kostenlos. Reicht fuer eine Karte mit 300 Markern vollkommen.
- **JSON als Datenformat**: Maschinenlesbar, einfach erweiterbar, kein DB-Setup noetig. `schema.json` validiert alle Eintraege.
- **Python-Scraper**: Requests + BeautifulSoup fuer klassisches Scraping, Mistral/Brave APIs fuer KI-gestuetzte Suche.
- **4-Phasen-Clean-Pipeline**: Validierung → Geocoding → Laender-/Qualitaetsfilter → Deduplizierung. Jede Phase isoliert und testbar.
- **Smart-Dedup**: Zuerst Adress-Hash und Website-Domain, dann aehnliche Namen (>75%). Mehrere Quellen werden gemerged, nicht geloescht.
- **Kein DB-Overhead**: 300 Datensaetze brauchen keine Datenbank. JSON ist git-freundlich und deployt sich von selbst.

## Datenqualitaet

| Phase | Was | Ergebnis |
|-------|-----|----------|
| Schema | jsonschema-Validierung aller Felder | 428/428 bestanden |
| Geocoding | (0,0)-Koordinaten via Nominatim nachschlagen | Alle Eintraege mit echten Koordinaten |
| QS | Mistral Large prueft Datenqualitaet | 6 Eintraege entfernt (Scheineintraege) |
| Dedup | Adress- und Namensaehnlichkeit erkennen | 132 Duplikate gemerged |
| **Final** | | **280 gepruefte Eintraege** |

## Bei mehr Zeit

- Oesterreich und Schweiz dazu — aktuell nur DE im Fokus
- Leaflet.markercluster fuer bessere Performance bei 300+ Markern
- Automatisierte Preisextraktion aus Labor-Websites
- FastAPI-Backend mit Such- und Filter-API
- CI/CD-Pipeline (GitHub Actions) fuer automatische Scraper-Laeufe
- Mehr Quellen: Google Maps API, Gelbe Seiten, Jameda-Scraping
