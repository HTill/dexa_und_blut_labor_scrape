# AGENTS.md

## Projekt

DEXA & Blutlabor Karte DACH — interaktive Web-Karte für Labore/Praxen.

## Strenge Regeln

- **Keine Secrets committen** — `.env`, API-Keys, Token gehören ins `.gitignore`.
- **Keine Build-Artefakte** — kein `dist/`, `build/`, `.pyc` ins Repo.
- **Kein Kommentar-Müll** — kein `# TODO: später mal`, kein auskommentierter Dead Code.
- **Dateien klein halten** — keine Monstermodule über 400 Zeilen. Lieber splitten.
- **README aktuell halten** — Setup muss auf einem frischen Rechner in 2 Minuten laufen.

## Code-Stil

- Python: `black`-kompatibel, type hints wo sinnvoll, docstrings bei öffentlichen Funktionen.
- JavaScript: modernes ES6+, keine globale Variablen-Verschmutzung.
- CSS: BEM oder einfache beschreibende Klassen, kein Inline-Style in JS.

## Testing

- **Python**: vor jedem Commit `pytest` laufen. Neue Funktionen brauchen Tests.
- **Web**: vor jedem Commit die Karte im Browser kurz manuell checken.
- Datenintegrität: `jsonschema`-Validierung aller Einträge gegen `data/schema.json`.

## Dokumentation

- Jede neue Funktion: kurzer Docstring / JSDoc-Kommentar, der erklärt WARUM, nicht WAS.
- Architektur-Entscheidungen kurz in `DECISIONS.md` dokumentieren.
- Scraping-Quellen und Datenherkunft in den JSON-Einträgen nachvollziehbar machen (`source`-Feld).

## Commits

- Kleine, atomare Commits. Kein "alles geht"-Commit.
- Message-Schema: `bereich: was wurde gemacht` (z.B. `scraper: Google Maps Places API eingebunden`)
- Englisch bevorzugt, Deutsch ok wenn der gesamte Repo-Kontext deutsch ist.

## Tech-Stack (nicht ohne Begründung ändern)

- Frontend: Leaflet.js + Vanilla JS + CSS — bewusst kein Framework.
- Backend/Daten: Python mit JSON als Speicher — bewusst keine DB nötig.
- Scraping: Python, requests, BeautifulSoup.
