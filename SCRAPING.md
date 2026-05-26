# SCRAPING.md — Scraping-Versuche & gefundene Einträge

Dokumentation aller Scraping-Ansätze für DEXA Body Composition & Blutlabor Anbieter im DACH-Raum.
Pro Suche/Session: Quelle, Query, Rohdaten, transformierte JSON-Einträge, Verifikationsstatus.

---

## Scraper-Architektur

### Verzeichnisstruktur

```
scraper/
├── tools/                    # Helfer (Model, Validierung, Clean-Pipeline)
│   ├── models.py             # Provider-Dataclass
│   ├── services.py           # Service Enum (type-safe Leistungs-Strings)
│   ├── data_kit.py           # DataKit — Provider erstellen + Datei-I/O
│   ├── request_kit.py        # RequestKit — HTTP mit Proxy, Rate-Limit, Retry
│   ├── validate.py           # jsonschema-Validierung
│   └── clean.py              # unchecked/*.json → providers.json (dedup)
│
├── scrapers/                 # Jeder Scraper in eigenem Ordner
│   └── manual/
│       └── run.py            # Interaktiver CLI-Scraper
│
├── tests/
│   ├── test_models.py
│   ├── test_services.py
│   ├── test_data_kit.py
│   ├── test_request_kit.py
│   ├── test_validate.py
│   └── test_clean.py
│
└── requirements.txt

data/
├── schema.json               # JSON Schema (wird getracked)
├── providers.json            # clean.py Output — lädt die Karte
└── unchecked/                # Scraper-Outputs (ignored von Git)
    └── ...
```

### DataKit — Provider-Erstellung und Datei-I/O

Jeder Scraper nutzt `DataKit`, um Provider zu erstellen und zu speichern:

```python
from scraper.tools.data_kit import DataKit

dk = DataKit("mein_scraper")  # Name → Dateiname in data/unchecked/

# Provider bauen mit Factory-Methoden
p = dk.provider(
    id="praxis-hannover",
    name="Praxis Hannover",
    category="dexa",
    address=dk.address(street="Str 1", postal_code="30159", city="Hannover", country="DE"),
    coordinates=dk.coordinates(lat=52.37, lng=9.73),
    services=[dk.svc.DEXA_BODY_COMP, dk.svc.BLOOD_SELF_PAYER],
    contact=dk.contact(phone="+49 511 123", website="https://..."),
    self_payer=True,
    prices={"DEXA Body Composition": "80 €"},
    verified=False,
    source=["mein_scraper"],
)

# Speichern / Laden
dk.save([p])
existing = dk.load()
```

### RequestKit — HTTP mit Proxy, Rate-Limiting und Retry

Wenn ein Scraper viele Requests an dieselbe API sendet, drohen IP-Sperren.
Ein **nginx-Forward-Proxy** auf einem separaten Server leitet Requests weiter —
die Zielseite sieht nur die Proxy-IP, nicht die des Scrapers.

```python
from scraper.tools.request_kit import RequestKit

# Ohne Proxy (direkt)
rk = RequestKit(rate=1.0, retries=3)

# Mit Proxy
rk = RequestKit(proxy="http://10.0.0.1:8080", rate=0.5, retries=5)

resp = rk.get("https://api.example.com/data", params={"key": "value"})
data = resp.json()
```

### Service Enum

Type-safe Strings für Leistungen. In `scraper/tools/services.py` definiert, über `dk.svc` nutzbar:

| Enum-Wert | String |
|---|---|
| `DEXA_BODY_COMP` | `"DEXA Body Composition"` |
| `DEXA_BONE_DENSITY` | `"DEXA Knochendichte"` |
| `BLOOD_SELF_PAYER` | `"Bluttest Selbstzahler"` |

Neue Services einfach im Enum ergänzen — Schema muss nicht angepasst werden.

### Workflow

1. Scraper bauen: `scraper/scrapers/<name>/run.py` — nutzt `DataKit` (+`RequestKit` für API-Scraper)
2. Scraper ausführen: `python -m scraper.scrapers.<name>.run` → schreibt `data/unchecked/<name>.json`
3. Manuelle Prüfung der Einträge in der unchecked-Datei
4. `python -m scraper.tools.clean` → validiert, dedupliziert, schreibt `data/providers.json`
5. Web-Karte (`web/`) lädt `providers.json`

### Manueller CLI-Scraper

```
python -m scraper.scrapers.manual.run
```

Interaktive Eingabe aller Felder: Name, Kategorie (DEXA/Blutlabor/Beides), Services, Adresse,
Koordinaten, Kontakt, Selbstzahler, Preise. Einträge werden mit `verified: true` gespeichert.

---

## Übersicht der Sessions

| # | Datum | Quelle | Ansatz | Roh-Ergebnisse | Verifizierte Einträge | Status |
|---|-------|--------|--------|---------------|----------------------|--------|
| 1 | _heute_ | Manuelle CLI | Interaktive Eingabe | — | — | **Aktiv** |

---

## Vorlage für neue Session

```markdown
## Session N — [Titel]

**Ziel:** [Was soll gefunden werden?]

**Quelle:** [API-Name, Suchmaschine, manuelle Recherche]

**Suchbegriff / Query:**
\`\`\`
...
\`\`\`

**Roh-Ergebnisse:** [Anzahl, erste Eindrücke]

**Herausforderungen / Erkenntnisse:**
- ...

**Gefundene JSON-Einträge:**

\`\`\`json
[
  {
    "id": "...",
    "name": "...",
    "category": "dexa | blutlabor | beide",
    "services": ["..."],
    "address": {
      "street": "...",
      "postal_code": "...",
      "city": "...",
      "country": "DE | AT | CH"
    },
    "coordinates": { "lat": 0.0, "lng": 0.0 },
    "contact": { "phone": "...", "website": "..." },
    "self_payer": true | false,
    "prices": {},
    "verified": false,
    "notes": "...",
    "source": ["..."]
  }
]
\`\`\`
```

---

## Mögliche nächste Quellen

| Quelle | Vorteil | Nachteil |
|--------|---------|----------|
| **Google Maps Places API** | Strukturierte Daten, Bewertungen, Website-Link | API-Kosten, Rate Limits |
| **Google Custom Search / Web-Suche** | Gezielte Suche nach "DEXA Body Composition [Stadt]" | Viel manuelle Nacharbeit |
| **Gelbe Seiten / Jameda / Doctolib** | Arztverzeichnisse mit Filter | Anti-Scraping-Maßnahmen |
| **Manuelle Recherche** | Höchste Datenqualität | Zeitaufwändig |
| **Firecrawl / Apify** | Website-Extraction, fertige Actors | Kostenpflichtig ab ~$29/Monat |
| **Nominatim / OSM** | Geocoding von Adressen → Koordinaten | Nur Geocoding, keine Discovery |

---

## Datenquellen-Bewertung

> Diese Tabelle wird nach jeder Session aktualisiert.

| Quelle | Geeignet für | Tauglichkeit | Begründung |
|--------|-------------|-------------|------------|
| Manuelle CLI | Verifizierte Einträge | ✅ Produktiv | Direkt schema-konform, `verified: true` |
