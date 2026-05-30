"""
Clean-Script: 5-Phasen-Pipeline.

1. Schema-Validierung
2. Geocoding — fehlende (0,0)-Koordinaten via Nominatim
3. Mistral Pass 1 — Datenqualitaet (Adresse, Telefon, Website plausibel?)
4. Mistral Pass 2 — Kategorie-Check (wirklich Bluttest/DEXA-Anbieter?)
5. Smart-Deduplizierung (aehnliche Namen, Adressen, Websites mergen)
"""

import json
import re
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

from scraper.tools.validate import validate_entry
from scraper.tools.mistral_kit import load_api_key, query_mistral, parse_json_response, check_website
from scraper.tools.geocode import geocode_entries

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
UNCHECKED_DIR = DATA_DIR / "unchecked"
OUTPUT_FILE = DATA_DIR / "providers.json"

QUALITY_PROMPT = """Du validierst Laboreintraege. Pruefe jeden Eintrag auf offensichtliche Fehler.

Jeder Eintrag hat ein "website_status" Feld:
- "ok" = Website erreichbar (HTTP 200)
- "no_url" = keine Website vorhanden
- "dead_404" = Website nicht gefunden (404)
- "dead_5xx" = Server-Fehler (500+)
- "dead_timeout" = keine Antwort innerhalb 10s
- "dead_no_connection" = Domain existiert nicht / kein Server erreichbar
- "dead_XXX" = anderer HTTP-Fehler

Markiere als BAD (quality: "bad") wenn:
- website_status ist "dead_*" → Anbieter existiert hoechstwahrscheinlich NICHT
- website_status ist "no_url" und Name/Adresse sehen erfunden aus
- Name ist Unsinn, Platzhalter oder kein Labor/keine Praxis
- Adresse enthaelt HTML, URLs oder ist unvollstaendig

Markiere als OK (quality: "ok") wenn:
- website_status ist "ok" und Name/Adresse sind plausibel
- website_status ist "no_url" aber Name/Adresse sehen nach echtem Labor aus

Bei "bad" kurzen Grund angeben (reason).

Input (JSON-Array):
{entries}

Output NUR dieses JSON-Array:
[
  {{"id": "entry-id", "quality": "ok"}},
  {{"id": "entry-id", "quality": "bad", "reason": "Website nicht erreichbar (dead_no_connection), Anbieter existiert nicht"}}
]"""

CATEGORY_PROMPTS = {
    "blutlabor": """Du prüfst ob Anbieter WIRKLICH Bluttests für SELBSTZAHLER anbieten.

Markiere als relevant (category_match: true) wenn:
- Es ist ein Direktlabor, IGeL-Labor oder privat zugaengliches Labor
- Die Website/Name deuten auf Labordiagnostik hin
- Es werden Blutuntersuchungen fuer Privatpatienten angeboten

Markiere als nicht relevant (category_match: false) wenn:
- Blutspendedienst (Haema, DRK, BSD, Blutspendezentrum)
- Reine Kassenarztpraxis ohne Selbstzahler-Hinweis
- Allgemeine Radiologie ohne Laborbezug
- Krankenhaus ohne separates Labor fuer Selbstzahler
- Name/Adresse deuten auf etwas anderes hin (Fitnesstudio, Apotheke, Kosmetik)

Input (JSON-Array mit id, name):
{entries}

Output NUR dieses JSON-Array:
[
  {{"id": "entry-id", "category_match": true}},
  {{"id": "entry-id", "category_match": false, "reason": "Blutspendedienst, kein Diagnostiklabor"}}
]""",
    "dexa": """Du pruefst ob Anbieter WIRKLICH DEXA-Ganzkoerper-Koerperfettmessungen anbieten.

Markiere als relevant (category_match: true) wenn:
- Radiologische Praxis mit DEXA/DXA-Bezug
- Sportmedizin mit Koerperfettanalyse
- Koerperanalyse-Studio/Body-Scan-Anbieter
- Endokrinologie mit DEXA
- Explizite Erwaehnung von Koerperzusammensetzung

Markiere als nicht relevant (category_match: false) wenn:
- Reine Knochendichtemessung (Osteoporose-Diagnostik) ohne Koerperfettanalyse
- Allgemeine Radiologie die nur Roentgen/CT/MRT macht
- Reine Blutlabore ohne DEXA
- Orthopädie ohne DEXA-Hinweis
- Name/Adresse deuten auf etwas anderes hin

Input (JSON-Array mit id, name):
{entries}

Output NUR dieses JSON-Array:
[
  {{"id": "entry-id", "category_match": true}},
  {{"id": "entry-id", "category_match": false, "reason": "Nur Knochendichtemessung, keine Koerperfettanalyse"}}
]"""
}


def load_unchecked_entries() -> list[dict]:
    """Lädt alle Einträge aus allen unchecked/*.json Dateien (nur Listen von Providern)."""
    if not UNCHECKED_DIR.exists():
        return []
    entries = []
    for filepath in sorted(UNCHECKED_DIR.glob("*.json")):
        if filepath.name == "search_cache.json":
            continue
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            entries.extend(data)
    return entries


def _batch(entries: list[dict], size: int = 15):
    for i in range(0, len(entries), size):
        yield entries[i : i + size]


def _make_entry_snippet(e: dict) -> dict:
    return {
        "id": e["id"],
        "name": e["name"],
        "address": e.get("address", {}),
        "contact": e.get("contact") or {},
        "category": e.get("category", ""),
    }


def _enrich_with_website_status(entries: list[dict], workers: int = 16) -> dict[str, str]:
    statuses: dict[str, str] = {}
    urls = [(e["id"], (e.get("contact") or {}).get("website", "") or "") for e in entries]
    urls = [(eid, url) for eid, url in urls if url]

    def _check_one(pair: tuple[str, str]) -> tuple[str, str]:
        eid, url = pair
        return eid, check_website(url)

    if urls:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_check_one, p): p for p in urls}
            for future in as_completed(futures):
                eid, status = future.result()
                statuses[eid] = status

    return statuses


def _normalize_address(addr: dict) -> str:
    parts = [addr.get("street", ""), addr.get("postal_code", ""), addr.get("city", "")]
    text = " ".join(p for p in parts if p).lower()
    text = re.sub(r"[^a-z0-9]", "", text)
    return text


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def deduplicate(entries: list[dict]) -> dict[str, dict]:
    """Dedupliziert nach ID. Erster Eintrag gewinnt, Sources werden gemerged."""
    result: dict[str, dict] = {}
    for e in entries:
        eid = e["id"]
        if eid in result:
            existing = result[eid]
            for s in e.get("source", []):
                if s not in existing.setdefault("source", []):
                    existing["source"].append(s)
        else:
            result[eid] = dict(e)
            result[eid].setdefault("source", list(e.get("source", [])))
    return result


def merge_sources(deduped: dict[str, dict]) -> list[dict]:
    """Konvertiert deduped dict zurück in eine Liste."""
    return list(deduped.values())


def _deduplicate_smart(entries: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)

    for e in entries:
        addr_key = _normalize_address(e.get("address", {}))[:20]
        website = (e.get("contact") or {}).get("website", "") or ""
        domain = re.sub(r"https?://(www\.)?", "", website).rstrip("/").lower()
        groups[addr_key].append(e)
        if domain:
            groups[f"web:{domain}"].append(e)

    merged_map: dict[str, dict] = {}
    seen_ids: set[str] = set()

    for key, group in groups.items():
        if len(group) < 2:
            for e in group:
                if e["id"] not in seen_ids:
                    merged_map[e["id"]] = e
                    seen_ids.add(e["id"])
            continue

        best = max(group, key=lambda e: len((e.get("contact") or {}).get("phone", "") or ""))
        for e in group:
            if e is best:
                continue
            for s in e.get("source", []):
                if s not in best.setdefault("source", []):
                    best["source"].append(s)
            if not best.get("contact") and e.get("contact"):
                best["contact"] = e["contact"]
        merged_map[best["id"]] = best
        for e in group:
            seen_ids.add(e["id"])

    result = []
    for e in entries:
        if e["id"] in seen_ids:
            result.append(merged_map.get(e["id"], e))
            seen_ids.discard(e["id"])

    name_groups: dict[str, list[dict]] = defaultdict(list)
    for e in result:
        found = False
        for key in list(name_groups.keys()):
            if _similar(e["name"], key) > 0.75:
                name_groups[key].append(e)
                found = True
                break
        if not found:
            name_groups[e["name"]].append(e)

    final = []
    done = set()
    for group in name_groups.values():
        if len(group) == 1:
            final.append(group[0])
        else:
            keeper = group[0]
            for other in group[1:]:
                for s in other.get("source", []):
                    if s not in keeper.setdefault("source", []):
                        keeper["source"].append(s)
            final.append(keeper)

    return final


def _mistral_pass(entries: list[dict], api_key: str, prompt_template: str,
                  pass_name: str, workers: int = 8,
                  enrich: dict[str, dict] | None = None) -> dict[str, dict]:
    results: dict[str, dict] = {}
    results_lock = threading.Lock()
    print_lock = threading.Lock()

    batches = list(_batch(entries))
    total = len(batches)
    done = [0]

    def _process(idx: int, batch: list[dict]) -> tuple[int, dict[str, dict]]:
        snippets = []
        for e in batch:
            s = _make_entry_snippet(e)
            if enrich and e["id"] in enrich:
                s.update(enrich[e["id"]])
            snippets.append(s)
        prompt = prompt_template.format(entries=json.dumps(snippets, ensure_ascii=False))
        local: dict[str, dict] = {}
        try:
            content = query_mistral(prompt, api_key)
            parsed = parse_json_response(content)
            for item in parsed:
                eid = item.get("id", "")
                if eid:
                    local[eid] = item
        except Exception:
            for e in batch:
                local[e["id"]] = {"id": e["id"], "quality": "ok"}
        with print_lock:
            done[0] += 1
            print(f"\r  Mistral {pass_name} [{done[0]}/{total}] ({len(results)} total)", end="", flush=True)
        return done[0], local

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process, i, b): i for i, b in enumerate(batches)}
        for future in as_completed(futures):
            _, local = future.result()
            with results_lock:
                results.update(local)

    print()
    return results


def clean(api_key: str | None = None, countries: set[str] | None = None) -> tuple[list[dict], list[str]]:
    raw = load_unchecked_entries()
    all_errors: list[str] = []
    valid: list[dict] = []

    # Phase 1: Schema
    print("Phase 1: Schema-Validierung ...")
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            all_errors.append(f"[entry-{i}] kein dict, typ={type(e).__name__}")
            continue
        errors = validate_entry(e)
        if errors:
            all_errors.extend(f"[{e.get('id', 'unknown')}] {err}" for err in errors)
        else:
            valid.append(e)
    print(f"  {len(valid)}/{len(raw)} schema-valid\n")

    # Phase 1b: Geocoding — fehlende Koordinaten via Nominatim
    geocoded = geocode_entries(valid, label="Geocoding")
    print()

    # Phase 1a: Country filter via address.country
    if countries:
        before = len(valid)
        valid = [e for e in valid if e.get("address", {}).get("country", "DE") in countries]
        print(f"Phase 1a: Länder-Filter ({','.join(sorted(countries))}) ...")
        print(f"  {before} -> {len(valid)} ({before - len(valid)} entfernt)\n")

    # Phase 2: Mistral Pass 1 — Datenqualitaet (mit Website-Check)
    if api_key and valid:
        print("Phase 2: Website-Check + Mistral Datenqualitaet ...")
        print(f"  Pruefe {sum(1 for e in valid if (e.get('contact') or {}).get('website'))} Websites ...")
        site_status = _enrich_with_website_status(valid)
        ok_count = sum(1 for v in site_status.values() if v == "ok")
        dead_count = sum(1 for v in site_status.values() if v.startswith("dead"))
        print(f"  ok: {ok_count}, dead: {dead_count} (davon 404: {sum(1 for v in site_status.values() if v == 'dead_404')}, no-conn: {sum(1 for v in site_status.values() if v == 'dead_no_connection')}, timeout: {sum(1 for v in site_status.values() if v == 'dead_timeout')})")
        enrich = {eid: {"website_status": status} for eid, status in site_status.items()}
        for e in valid:
            if e["id"] not in enrich:
                enrich[e["id"]] = {"website_status": "no_url"}
        qr = _mistral_pass(valid, api_key, QUALITY_PROMPT, "Qualitaet", enrich=enrich)
        bad_ids = {eid for eid, r in qr.items() if r.get("quality") == "bad"}
        removed_quality = sum(1 for e in valid if e["id"] in bad_ids)
        valid = [e for e in valid if e["id"] not in bad_ids]
        print(f"  {removed_quality} Eintraege entfernt, {len(valid)} verbleiben\n")
    else:
        print("Phase 2: Uebersprungen (kein API-Key)\n")



    # Phase 4: Smart Deduplication
    print("Phase 4: Smart-Deduplizierung ...")
    before = len(valid)
    valid = _deduplicate_smart(valid)
    print(f"  {before} -> {len(valid)} ({before - len(valid)} Duplikate merged)\n")

    valid.sort(key=lambda x: x.get("name", "").lower())
    return valid, all_errors


def main() -> None:
    api_key = load_api_key()

    countries: set[str] | None = {"DE"}
    for arg in sys.argv[1:]:
        if arg.startswith("--country="):
            val = arg.split("=", 1)[1].upper()
            countries = {c.strip() for c in val.split(",") if c.strip()}
        elif arg == "--country":
            idx = sys.argv.index(arg)
            if idx + 1 < len(sys.argv):
                val = sys.argv[idx + 1].upper()
                countries = {c.strip() for c in val.split(",") if c.strip()}

    print(f"Länder-Filter: {sorted(countries)}\n")

    merged, errors = clean(api_key, countries=countries)

    if errors:
        print(f"⚠ {len(errors)} Validierungsfehler:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    cats = defaultdict(int)
    for e in merged:
        cats[e.get("category", "?")] += 1
    print(f"✓ {len(merged)} Eintraege nach data/providers.json geschrieben")
    for cat, count in sorted(cats.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
