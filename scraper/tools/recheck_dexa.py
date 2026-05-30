"""DEXA re-verification script via opencode agent.

Re-checks all DEXA entries in providers.json: visits each website and verifies
whether the practice actually offers DEXA body composition (Koerperfettanalyse),
not just bone density measurement (Knochendichtemessung).

Uses kimi-k2.6 (multimodal) for screenshot-based verification.

Usage:
    python -m scraper.tools.recheck_dexa           # dry-run: print verdicts
    python -m scraper.tools.recheck_dexa --apply   # write cleaned providers.json

Output:
    Overwrites data/providers.json with cleaned entries.
"""

import json
import sys
from pathlib import Path

from scraper.tools.opencode_pipeline import AGENT_MODEL, AGENT_WORKERS, _run_agent

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
PROVIDERS_FILE = DATA_DIR / "providers.json"

REVERIFY_PROMPT = """Du bist ein DEXA-Verifikations-Agent. Deine Aufgabe ist es, EXAKT zu pruefen ob eine Praxis DEXA-GANZKOERPER-KOERPERFETTANALYSE (Body Composition) anbietet.

ZU PRUEFENDE WEBSITE: {url}

SCHRITTE:
1. Lade die Website mit WebFetch. Starte auf der Startseite.
2. Rufe zusaetzlich diese Unterseiten auf falls vorhanden: "Leistungen", "DEXA", "Diagnostik", "Praxis", "Vorsorge", "Preise".
3. Lies den gesamten Textinhalt gruendlich.
4. Suche EXPLIZIT nach diesen Begriffen im Text:
   - "Koerperzusammensetzung"
   - "Koerperfettanalyse"
   - "Body Composition"
   - "Ganzkoerperanalyse"
   - "Koerperfettmessung"
   - "Fettfreie Masse"
   - "Muskelmasse" in Kombination mit "Fettmasse"

UNTERSCHEIDUNG (SEHR WICHTIG):
- Seite erwaehnt NUR "Knochendichtemessung", "Osteoporose", "Osteodensitometrie" -> NICHT relevant!
- ACHTUNG: Nur weil in einem Text allgemein erklaert wird, dass ein DXA-Geraet theoretisch auch Koerperzusammensetzung messen kann, reicht das NICHT aus!
- Die Praxis muss EXPLIZIT den Body Composition / Ganzkoerperscan als **konkretes, buchbares Leistungsangebot fuer Patienten** anpreisen oder in einer Preisliste/Leistungsliste fuehren.
- Eine Praxis die DXA nur fuer Knochendichte nutzt, aber beilaeufig Koerperzusammensetzung als allgemeine Information erwaehnt, ist NICHT relevant.
- Nur wenn die Praxis Koerperfett/Koerperzusammensetzung als konkreten Service bewirbt -> RELEVANT.

WICHTIG: Deine finale Ausgabe MUSS NUR diesen exakten JSON-Block enthalten. NICHTS anderes.

```json
{{
  "is_body_comp": true,
  "evidence": "Auf der Leistungsseite steht woertlich: 'Ganzkoerperanalyse mit DXA zur Bestimmung von Koerperfett und Muskelmasse'",
  "url_found": "https://example.com/leistungen/ganzkoerperanalyse"
}}
```

Wenn Body Composition NICHT explizit als Leistung angeboten wird (oder z.B. nur beilaeufig erwaehnt wird, dass das Geraet es theoretisch kann):
```json
{{
  "is_body_comp": false,
  "evidence": "Seite erklaert nur allgemein die Funktion von DXA, listet aber Body Composition nicht als buchbare Leistung fuer Patienten auf.",
  "url_found": "https://example.com/leistungen/dxa"
}}
```"""


def load_dexa_entries() -> list[dict]:
    if not PROVIDERS_FILE.exists():
        return []
    with open(PROVIDERS_FILE, encoding="utf-8") as f:
        entries = json.load(f)
    return [e for e in entries if e.get("category") == "dexa"]


def recheck_entries(entries: list[dict], workers: int = AGENT_WORKERS) -> list[dict]:
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, dict] = {}
    lock = threading.Lock()

    def _verify(entry: dict) -> tuple[str, dict]:
        eid = entry["id"]
        name = entry.get("name", "?")
        url = (entry.get("contact") or {}).get("website", "")
        if not url:
            return eid, {"is_body_comp": False, "evidence": "No website URL", "url_found": None}

        print(f"  Checking: {name} ({url[:60]}...)")
        result = _run_agent(url, REVERIFY_PROMPT, model=AGENT_MODEL)
        if result:
            return eid, result
        return eid, {"is_body_comp": False, "evidence": "Agent failed to produce result", "url_found": None}

    print(f"\nRe-verifying {len(entries)} DEXA entries ({workers} workers)...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(_verify, e): e for e in entries}
        for i, f in enumerate(as_completed(futures), 1):
            eid, result = f.result()
            with lock:
                results[eid] = result
                is_bc = result.get("is_body_comp", False)
                status = "BODY_COMP" if is_bc else "BONE_ONLY"
                print(f"  [{i}/{len(entries)}] {eid}: {status}")

    return results


def apply_results(verdicts: dict[str, dict], dry_run: bool = True) -> int:
    if not PROVIDERS_FILE.exists():
        print("providers.json not found")
        return 0

    with open(PROVIDERS_FILE, encoding="utf-8") as f:
        entries = json.load(f)

    removed = 0
    changed = 0
    kept = 0
    cleaned = []

    for e in entries:
        eid = e["id"]
        if e.get("category") == "dexa":
            verdict = verdicts.get(eid)
            if verdict and not verdict.get("is_body_comp", False):
                print(f"  REMOVE: {e['name']} -> {verdict.get('evidence', 'no evidence')[:100]}")
                removed += 1
                continue
            else:
                kept += 1
        cleaned.append(e)

    print(f"\n  {kept} DEXA kept, {removed} removed, {len(entries)} total")

    if not dry_run:
        with open(PROVIDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
        print(f"  Written to {PROVIDERS_FILE}")

    return removed


def main() -> None:
    dry_run = "--apply" not in sys.argv

    entries = load_dexa_entries()
    if not entries:
        print("No DEXA entries found in providers.json")
        return

    print(f"Found {len(entries)} DEXA entries to re-verify")
    if dry_run:
        print("DRY-RUN mode (use --apply to write changes)\n")

    verdicts = recheck_entries(entries)
    apply_results(verdicts, dry_run=dry_run)

    if dry_run:
        print("\nRe-run with --apply to commit changes.")


if __name__ == "__main__":
    main()
