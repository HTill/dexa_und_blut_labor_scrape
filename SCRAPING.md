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
│   └── overpass/
│       └── scraper.py
│
├── tests/
│   ├── test_models.py
│   ├── test_services.py
│   ├── test_kit.py
│   ├── test_validate.py
│   └── test_clean.py
│
└── requirements.txt

data/
├── schema.json               # JSON Schema (wird getracked)
├── providers.json            # clean.py Output — lädt die Karte
└── unchecked/                # Scraper-Outputs (ignored von Git)
    ├── overpass_dach.json
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

**nginx-Proxy einrichten (auf eigenem Server):**
```nginx
# /etc/nginx/sites-available/scraper-proxy
server {
    listen 8080;
    location / {
        resolver 8.8.8.8;
        proxy_pass $scheme://$host$request_uri;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

Mehrere Proxies auf verschiedenen Servern = rotierende IPs = kein Block.

### Service Enum

Type-safe Strings für Leistungen. In `scraper/tools/services.py` definiert, über `kit.svc` nutzbar:

| Enum-Wert | String |
|---|---|
| `DEXA_BODY_COMP` | `"DEXA Body Composition"` |
| `DEXA_BONE_DENSITY` | `"DEXA Knochendichte"` |
| `BLOOD_SELF_PAYER` | `"Bluttest Selbstzahler"` |

Neue Services einfach im Enum ergänzen — Schema muss nicht angepasst werden.

### Workflow

1. Scraper bauen: `scraper/scrapers/<name>/run.py` — nutzt `DataKit` + `RequestKit`
2. Scraper ausführen: `python -m scraper.scrapers.<name>.run` → schreibt `data/unchecked/<name>.json`
3. Manuelle Prüfung der Einträge in der unchecked-Datei
4. `python -m scraper.tools.clean` → validiert, dedupliziert, schreibt `data/providers.json`
5. Web-Karte (`web/`) lädt `providers.json`

---

## Übersicht der Sessions

| # | Datum | Quelle | Ansatz | Roh-Ergebnisse | Verifizierte Einträge | Status |
|---|-------|--------|--------|---------------|----------------------|--------|
| 0 | 2026-05-26 | Overpass API | `amenity=doctors` + `healthcare:speciality=radiology` in DE | ~700 Nodes | 0 | **Prototyp – nur Discovery** |

---

## Session 0 — Overpass API: Radiologie-Praxen in DE

**Ziel:** Breitflächige Discovery von Radiologie-Praxen in Deutschland als Kandidaten für manuelle Nachprüfung (Body Comp vs. Knochendichte).

**Quelle:** OpenStreetMap Overpass API (`https://overpass-api.de/api/interpreter`)

**Query:**
```
[out:json];
area["ISO3166-1"="DE"];
node["amenity"="doctors"]["healthcare:speciality"~"radiology"](area);
out center;
```

**Ergebnis:** ~700 Nodes mit lat/lng und Tags, aber ...

**Probleme:**
- Overpass unterscheidet **nicht** zwischen Body Composition und reiner Knochendichtemessung
- Keine Aussage zu Selbstzahler-Möglichkeit
- Keine Blutlabor-Daten enthalten
- Viele Einträge sind Klinik-Radiologien ohne Body-Comp-Angebot
- Keine Website/Telefon-Nummer in den meisten Tags

**Fazit:** Overpass eignet sich nur als **erster Discovery-Schritt**. Jeder Kandidat muss einzeln per Website geprüft werden.

**Gefundene verifizierte Einträge:** 0 (nicht als verifizierbare Einträge geeignet)

---

## Session 1 — [Nächste Suche hier dokumentieren]

**Ziel:** _..._

**Quelle:** _z.B. Google Maps Places API, Web-Suche, manuelle Recherche_

**Suchbegriff / Query:** _..._

**Roh-Ergebnisse:** _Anzahl, Qualität_

**Herausforderungen / Erkenntnisse:** _..._

**Gefundene JSON-Einträge:**

```json
[
  // ...
]
```

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
    "contact": {
      "phone": "...",
      "website": "..."
    },
    "self_payer": true | false,
    "prices": {},
    "verified": false,
    "notes": "...",
    "source": "..."
  }
]
\`\`\`
```

---

## Mögliche nächste Quellen (Ideen)

| Quelle | Vorteil | Nachteil |
|--------|---------|----------|
| **Google Maps Places API** | Strukturierte Daten, Bewertungen, Website-Link | API-Kosten, Rate Limits, nicht alle Praxen gelistet |
| **Google Custom Search / Web-Suche** | Gezielte Suche nach "DEXA Body Composition Selbstzahler [Stadt]" | Viel manuelle Nacharbeit, unstrukturiert |
| **Gelbe Seiten / Jameda / Doctolib** | Arztverzeichnisse mit Filter | Anti-Scraping-Maßnahmen, Terms of Service |
| **Manuelle Recherche** | Höchste Datenqualität | Zeitaufwändig, skaliert nicht |
| **Overpass (verfeinert)** | Kostenlos, keine Rate Limits | Keine Unterscheidung Body Comp vs. Knochendichte, keine Kontaktdaten |
| **Nominatim / OSM** | Geocoding von Adressen → Koordinaten | Nur Geocoding, keine Discovery |

---

## Datenquellen-Bewertung (was hat funktioniert, was nicht)

> Diese Tabelle wird nach jeder Session aktualisiert.

| Quelle | Geeignet für | Tauglichkeit | Begründung |
|--------|-------------|-------------|------------|
| Overpass API | Discovery | ⚠️ Eingeschränkt | Nur Kategorie-Recognition, keine Detaildaten, keine Body-Comp-Unterscheidung |
