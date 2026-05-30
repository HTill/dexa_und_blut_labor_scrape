# SCRAPING.md — Scraping-Methoden & Scraper-Dokumentation

Dokumentation aller Scraper fuer DEXA Body Composition & Blutlabor Anbieter im DACH-Raum.

Zwei Methoden:

- **Methode A**: Bekannte grosse Anbieter direkt scrapen — alle Locations einer Laborkette auf einmal einsammeln.
- **Methode B**: Websuche + Agenten-Check — Brave Search findet Kandidaten, opencode-Agenten pruefen jede Website.

---

## Methode A: Grosse Anbieter mit mehreren Standorten

Scraper die direkt die Website eines bekannten Labor- oder Praxisnetzwerks parsen und alle Standort-Detailseiten extrahieren.

### aeon

| Feld | Wert |
|------|------|
| Quell-URL | `https://aeon.life/de-de/standorte/` |
| Kategorie | DEXA |
| Technik | Nuxt 3 SSR-State-Payload parsen (Storyblok CMS) |
| Locations | 15 (8 DE, 7 CH) |
| Besonderheit | Keine klassische HTML-Scraping — JSON aus `window.__NUXT__` extrahiert |

Aeon bietet MRI-Ganzkoerper-Checks in Deutschland und der Schweiz. Zusaetzlich zum MRI-Scan wird ein DEXA Body Composition Scan als optionale Leistung angeboten (~10 min). DEXA-Preise sind nicht oeffentlich auf der Seite, muessen angefragt werden.

### imd

| Feld | Wert |
|------|------|
| Quell-URLs | `imd-berlin.de`, `imd-potsdam.de`, `imd-greifswald.de`, `imd-oderland.de` |
| Kategorie | Blutlabor |
| Technik | HTML-Scraping (BeautifulSoup) |
| Locations | Berlin + 3 Partnerlabore |
| Besonderheit | 4 separate Websites einer Labor-Gruppe |

IMD (Institut fuer Medizinische Diagnostik) ist ein Laborverbund im Raum Berlin/Brandenburg. Der Berliner Hauptstandort wird von der Website gescrapt, die Partnerstandorte (Potsdam, Greifswald, Oderland) sind als feste Daten hinterlegt.

### ladr

| Feld | Wert |
|------|------|
| Quell-URL | `https://www.ladr.de/ein-starker-verbund/labor-vor-ort/facharztlabore/` |
| Kategorie | Blutlabor |
| Technik | HTML-Scraping (BeautifulSoup) der 18 Detailseiten |
| Locations | 18 Facharztlabore |
| Besonderheit | Basislabore (Laborgemeinschaften) explizit ausgeschlossen — kein Publikumsverkehr |

LADR ist ein grosses deutsches Labornetzwerk. Nur Facharztlabore mit Patientenverkehr werden gescrapt; Basis-/Einsendelabore (reine Probenannahmestellen fuer Aerzte) werden ignoriert. Selbstzahler-Info wird zusaetzlich von der IGEL-Seite bezogen.

### meindirektlabor

| Feld | Wert |
|------|------|
| Quell-URL | `https://www.meindirektlabor.de/standorte/` |
| Kategorie | Blutlabor |
| Technik | HTML-Scraping (BeautifulSoup), Geocoding via Nominatim |
| Locations | Uebersichtsseite + Detailseiten |
| Besonderheit | Alle Standorte sind explizit Selbstzahler-Labore |

MeinDirektlabor ist ein reiner Selbstzahler-Direktlabor-Service der Bioscientia-Gruppe. Keine Ueberweisung noetig, Preise transparent auf der Website. Perfekt fuer den Use Case.

### synlab

| Feld | Wert |
|------|------|
| Quell-URL | `https://www.synlab.de/lablocator` |
| Kategorie | Blutlabor |
| Technik | HTML-Scraping (BeautifulSoup) des LabLocators |
| Locations | Alle DE-Standorte |
| Besonderheit | Groesstes deutsches Labornetzwerk, konservatives Rate-Limiting (0.5s) |

Synlab ist der groesste Laboranbieter in Deutschland. Der LabLocator listet alle Blutabnahme-Standorte. Selbstzahler-Status muss pro Standort verifiziert werden.

### wisplinghoff

| Feld | Wert |
|------|------|
| Quell-URLs | `https://www.wisplinghoff.de/das-labor/standort-*` (8 Standorte) |
| Kategorie | Blutlabor |
| Technik | HTML-Scraping (BeautifulSoup), Geocoding via Nominatim |
| Locations | 8 Standorte (Aachen, Berlin, Bonn, Delmenhorst, Frankfurt, Herne, Kempen) |
| Besonderheit | URLs als feste Liste vorgegeben |

Wisplinghoff ist ein mittelgrosses Labor mit Standorten in NRW, Berlin und Frankfurt. Die Standort-URLs folgen einem klaren Schema und sind hartkodiert.

---

## Methode B: Websuche mit Agenten-Check

Zweistufig: Brave Search liefert Kandidaten-URLs, opencode-Agenten pruefen jede Website auf Relevanz und extrahieren strukturierte Daten.

Die Pipeline ist in `scraper/tools/opencode_pipeline.py` implementiert und wird von beiden Such-Scrapern genutzt.

### Pipeline-Stufen

```
Stage 1: Brave Search (cached)
  → URLs + Snippets fuer jede Query in jeder Stadt

Stage 2: HEAD-Check
  → Nur erreichbare URLs (HTTP-Status, Timeout 10s)

Stage 3: Mistral Snippet-Filter
  → LLM prueft Snippets auf Relevanz (Bluttest/DEXA?)

Stage 4: opencode Agent (parallel)
  → KI-Agent besucht Website, extrahiert JSON

Stage 5: Geocoding
  → Nominatim fuer (0,0)-Koordinaten
```

### blutlabor_opencode_search

| Feld | Wert |
|------|------|
| Queries | "IGeL Leistung Bluttests", "Blutwerte testen lassen privat" |
| Kategorie | Blutlabor |
| Suchraum | TOP100_CITIES (100 groesste deutsche Staedte) |
| Besonderheit | Prueft auf Selbstzahler-Eignung und echte Labordiagnostik |

Der opencode-Agent besucht jede gefundene Website und prueft: Bietet die Praxis Blutuntersuchungen fuer Selbstzahler an? Gibt es eine Preisliste? Ist es ein Diagnostiklabor oder nur eine Blutspende?

### dexa_opencode_search

| Feld | Wert |
|------|------|
| Queries | "DEXA Koerperfettmessung", "DEXA Ganzkoerper Scan", "DXA Ganzkoerperanalyse", etc. |
| Kategorie | DEXA |
| Suchraum | TOP100_CITIES (100 groesste deutsche Staedte) |
| Besonderheit | Unterscheidet Koerperfettmessung vs. reine Knochendichtemessung |

Kritische Unterscheidung: viele Praxen bieten DEXA fuer Osteoporose-Diagnostik an (Knochendichte), aber nicht fuer Body Composition (Koerperfett/Muskelmasse). Der Agent prueft explizit auf `has_body_composition`.

---

## Manueller Scraper

| Feld | Wert |
|------|------|
| Typ | Interaktive CLI |
| Kategorie | Beide |
| Befehl | `python -m scraper.scrapers.manual.run` |
| Besonderheit | `verified: true` — manuell gepruefte Eintraege |

Fuer Einzeleintraege oder Nachpflege. Fragt alle Felder interaktiv ab und haengt sie an `data/unchecked/manual.json` an.

---

## Scraper-Architektur

### DataKit — Provider-Erstellung und Datei-I/O

Jeder Scraper nutzt `DataKit`, um schema-konforme Provider-Eintraege zu bauen und automatisch nach `data/unchecked/<name>.json` zu schreiben.

```python
from scraper.tools.data_kit import DataKit

dk = DataKit("mein_scraper")

p = dk.provider(
    id="praxis-hannover",
    name="Praxis Hannover",
    category="blutlabor",
    address=dk.address(street="Str 1", postal_code="30159", city="Hannover", country="DE"),
    coordinates=dk.coordinates(lat=52.37, lng=9.73),
    services=[dk.svc.BLOOD_SELF_PAYER],
    contact=dk.contact(phone="+49 511 123", website="https://..."),
    self_payer=True,
    verified=False,
    source=["mein_scraper"],
)

dk.save([p])
```

### RequestKit — HTTP mit Rate-Limiting und Retry

```python
from scraper.tools.request_kit import RequestKit

rk = RequestKit(rate=0.5, retries=3)  # 0.5s zwischen Requests, 3 Retries
resp = rk.get("https://example.com", params={"key": "value"})
```

---

## Workflow

1. Scraper ausfuehren: `python -m scraper.scrapers.<name>.run` → schreibt `data/unchecked/<name>.json`
2. Manuelle Pruefung der unchecked-Datei (optional)
3. `python -m scraper.tools.clean` → validiert, geocoded, filtert, dedupliziert → `data/providers.json`
4. Web-Karte (`web/`) laedt `providers.json` direkt per `fetch()`
