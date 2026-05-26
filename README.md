# DEXA & Blutlabor Scrape — Interaktive Karte DACH

Webanwendung zur Suche von DEXA Body Composition Scans und Blutlaboren (Selbstzahler) in Deutschland, Österreich und der Schweiz.

## Setup

```bash
git clone git@github.com:HTill/dexa_und_blut_labor_scrape.git
cd dexa_und_blut_labor_scrape

# Web-Karte starten (braucht nur einen Browser)
open web/index.html
# oder:
python3 -m http.server 8000 --directory web
```

## Struktur

```
├── README.md
├── BEWERBUNGSAUFGABE.md      # Original-Aufgabenstellung
├── data/
│   ├── schema.json           # JSON Schema für Anbieterdaten
│   └── providers.json        # Erfasste Anbieter
├── scraper/
│   ├── requirements.txt
│   └── scrape.py             # Scraping-Skripte
└── web/
    ├── index.html            # Kartenansicht
    ├── style.css
    └── app.js
```

## Entscheidungen

- **Leaflet.js** für die Karte: leichtgewichtig, kein Build-Tool nötig, OpenStreetMap-Tiles kostenlos.
- **JSON** als Datenformat: maschinenlesbar, einfach erweiterbar, ohne Datenbank-Setup.
- **Python** für Scraping: Requests + BeautifulSoup, bewährt und schnell produktiv.
- **Kein Framework-Overhead**: Die Aufgabe verlangt eine funktionale Karte, keine SPA. Vanilla JS + Leaflet reicht.

## Bei mehr Zeit

- GeoJSON statt Flat-JSON für direkte Leaflet-Kompatibilität
- Clustering bei vielen Markern (Leaflet.markercluster)
- Backend mit FastAPI + SQLite für Filter/Suche
- Docker-Compose für Ein-Klick-Start
- Automatisiertes Geocoding per Nominatim-API
- Duplikat-Erkennung über Adress-Hashing
