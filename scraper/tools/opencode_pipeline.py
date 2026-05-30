"""Shared opencode-based search pipeline for DEXA and Blutlabor.

4-stage funnel + Stage 5 geocoding:
  1. Brave Search (cached) → URLs + Snippets
  2. HEAD-Check → nur erreichbare URLs
  3. Mistral Snippet-Filter → nur relevante URLs
  4. opencode Agenten (parallel) → strukturierte JSON-Extraktion
  5. Geocoding → Nominatim für (0,0)-Koordinaten

Usage:
    from scraper.tools.opencode_pipeline import run_search_pipeline, PipelineConfig

    config = PipelineConfig(
        name="dexa_search", category="dexa",
        service="DEXA Body Composition", queries=["DEXA Koerperfettmessung ...", ...],
        prompt_template=DEXA_PROMPT, id_prefix="dexa-",
        extra_validate=lambda r: r.get("has_body_composition", True),
        include_prices=True, self_payer_from=True,
    )
    run_search_pipeline(config)
"""

import json
import os
import re
import subprocess
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from scraper.tools.brave_kit import search as brave_search
from scraper.tools.data_kit import DataKit
from scraper.tools.geocode import geocode_entries
from scraper.tools.mistral_kit import check_website, filter_urls_by_snippet, load_api_key

TOP100_CITIES = [
    "Berlin", "Hamburg", "Muenchen", "Koeln", "Frankfurt am Main",
    "Stuttgart", "Duesseldorf", "Leipzig", "Dortmund", "Essen",
    "Bremen", "Dresden", "Hannover", "Nuernberg", "Duisburg",
    "Bochum", "Wuppertal", "Bielefeld", "Bonn", "Muenster",
    "Mannheim", "Karlsruhe", "Augsburg", "Wiesbaden", "Moenchengladbach",
    "Gelsenkirchen", "Aachen", "Braunschweig", "Kiel", "Chemnitz",
    "Halle", "Magdeburg", "Freiburg", "Krefeld", "Luebeck",
    "Oberhausen", "Erfurt", "Mainz", "Rostock", "Kassel",
    "Hagen", "Potsdam", "Saarbruecken", "Hamm", "Ludwigshafen",
    "Oldenburg", "Osnabrueck", "Leverkusen", "Heidelberg", "Darmstadt",
    "Solingen", "Regensburg", "Paderborn", "Ingolstadt", "Wuerzburg",
    "Wolfsburg", "Ulm", "Offenbach", "Recklinghausen", "Goettingen",
    "Heilbronn", "Pforzheim", "Bottrop", "Trier", "Reutlingen",
    "Bremerhaven", "Koblenz", "Bergisch Gladbach", "Jena", "Remscheid",
    "Erlangen", "Moers", "Salzgitter", "Siegen", "Hildesheim",
    "Cottbus", "Kaiserslautern", "Guetersloh", "Witten", "Schwerin",
    "Gera", "Zwickau", "Esslingen", "Dueren", "Ludwigsburg",
    "Iserlohn", "Ratingen", "Marl", "Luenen", "Hanau",
    "Velbert", "Flensburg", "Tuebingen", "Minden", "Villingen-Schwenningen",
]

BLOCKED_DOMAINS = {
    "google.com", "youtube.com", "facebook.com", "instagram.com",
    "twitter.com", "x.com", "linkedin.com", "wikipedia.org",
    "amazon.de", "ebay.de", "reddit.com", "tiktok.com",
    "pinterest.com", "yelp", "jameda.de", "doctolib.de",
    "sanego.de", "gelbeseiten.de", "dasoertliche.de",
}

AGENT_TIMEOUT = 600
AGENT_WORKERS = 6
AGENT_MODEL = "opencode-go/kimi-k2.6"

NVM_BIN = os.path.expanduser("~/.nvm/versions/node/v24.14.1/bin")


class PipelineConfig:
    def __init__(
        self,
        *,
        name: str,
        category: str,
        service: str,
        queries: list[str],
        prompt_template: str,
        id_prefix: str,
        extra_validate: Callable[[dict], bool] | None = None,
        include_prices: bool = False,
        self_payer_from: str | bool = True,
    ):
        self.name = name
        self.category = category
        self.service = service
        self.queries = queries
        self.prompt_template = prompt_template
        self.id_prefix = id_prefix
        self.extra_validate = extra_validate
        self.include_prices = include_prices
        self.self_payer_from = self_payer_from


def _is_blocked(url: str) -> bool:
    domain = urlparse(url).netloc.lower().replace("www.", "")
    return any(b in domain for b in BLOCKED_DOMAINS)


def _run_agent(url: str, prompt_template: str, model: str | None = None) -> dict | None:
    prompt = prompt_template.replace("{url}", url)
    env = {k: v for k, v in os.environ.items() if not k.startswith("OPENCODE_")}
    path = env.get("PATH", "/usr/bin")
    if path and NVM_BIN not in path:
        env["PATH"] = f"{NVM_BIN}:{path}"
    env["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expanduser("~/.cache/ms-playwright")
    cmd = ["opencode", "run", "--dangerously-skip-permissions"]
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)
    output = ""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=AGENT_TIMEOUT, env=env,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        print(f"      TIMEOUT")
        return None
    except Exception as e:
        print(f"      ERROR: {e}")
        return None

    try:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        match = re.search(r"(\{[^{}]*\"is_target\"[^{}]*\})", output, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except (json.JSONDecodeError, IndexError, AttributeError):
        pass
    return None


def run_search_pipeline(config: PipelineConfig) -> None:
    api_key = load_api_key()
    if not api_key:
        print("FEHLER: MISTRAL_API_KEY nicht gefunden!")
        return

    dk = DataKit(config.name)

    total_queries = len(TOP100_CITIES) * len(config.queries)
    print(f"=== {config.name} opencode Pipeline ===\n")
    print(f"Staedte: {len(TOP100_CITIES)} | Queries: {len(config.queries)} | Brave-Aufrufe: {total_queries}")
    print()

    # === STAGE 1: Brave Search ===
    print("Stage 1: Brave Search (cached, rich results) ...")
    all_results: list[dict] = []
    seen_urls: set[str] = set()
    for city in TOP100_CITIES:
        for query in config.queries:
            full_query = f"{query} {city}"
            for r in brave_search(full_query):
                url = r.get("url", "")
                if url.startswith("http") and not _is_blocked(url) and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
    print(f"  {len(all_results)} unique results nach Dedup + Block-Filter\n")

    # === STAGE 2: HEAD Check ===
    print("Stage 2: HEAD-Check (parallel) ...")
    alive_results: list[dict] = []
    dead_count = 0

    def _check(r):
        url = r.get("url", "")
        status = check_website(url)
        return r, status

    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(_check, r): r for r in all_results}
        for f in as_completed(futures):
            r, status = f.result()
            if status == "ok":
                alive_results.append(r)
            else:
                dead_count += 1
    print(f"  {len(alive_results)} alive, {dead_count} dead\n")

    # === STAGE 3: Mistral Rich-Snippet-Filter ===
    print("Stage 3: Mistral URL-Relevanz-Filter (mit Brave Rich-Data) ...")
    filtered_urls = filter_urls_by_snippet(alive_results, api_key)
    print(f"  {len(alive_results)} -> {len(filtered_urls)} als relevant eingestuft\n")

    # === STAGE 4: opencode Agents ===
    print(f"Stage 4: opencode Agents ({len(filtered_urls)} URLs, {AGENT_WORKERS} parallel, {AGENT_TIMEOUT}s timeout) ...")
    all_providers: list = []
    all_map: dict[str, object] = {}

    existing = dk.load()
    for p in existing:
        all_map[f"{p.name}|{p.address.city}"] = p
    if all_map:
        print(f"  (resume: {len(all_map)} existing providers loaded)")

    lock = threading.Lock()
    done = [0]
    failed = [0]

    def _process(url: str):
        result = _run_agent(url, config.prompt_template, model=AGENT_MODEL)
        with lock:
            done[0] += 1
            if result and result.get("is_target"):
                name = (result.get("name") or "").strip()[:100]
                city = (result.get("city") or "").strip()
                country = (result.get("country") or "DE").strip().upper()

                valid = bool(name and city and country in ("DE", "AT", "CH"))
                if config.extra_validate and valid:
                    valid = config.extra_validate(result)

                if valid:
                    slug = re.sub(r"[^a-z0-9-]", "", name.lower())[:30]
                    city_slug = re.sub(r"[^a-z0-9-]", "", city.lower())[:30]
                    pid = f"{config.id_prefix}{slug}-{city_slug}"
                    if pid in all_map:
                        pid += f"-{len(all_map)}"

                    self_payer = config.self_payer_from
                    if isinstance(self_payer, str):
                        self_payer = result.get(self_payer, True)

                    prices = result.get("prices") if config.include_prices else None

                    provider = dk.provider(
                        id=pid, name=name, category=config.category,
                        address=dk.address(
                            street=(result.get("street") or "").strip(),
                            postal_code=(result.get("postal_code") or "").strip(),
                            city=city, country=country,
                        ),
                        coordinates=dk.coordinates(lat=0.0, lng=0.0),
                        services=[config.service],
                        contact=dk.contact(
                            phone=result.get("phone") or None,
                            website=url,
                            email=result.get("email") or None,
                        ),
                        self_payer=self_payer,
                        prices=prices,
                        verified=True,
                        docs=f"Verifiziert via opencode Agent. Website: {url}",
                        source=[url],
                    )
                    all_map[pid] = provider
                    all_providers = list(all_map.values())
                    dk.save(all_providers)
            else:
                failed[0] += 1
            print(f"\r  [{done[0]}/{len(filtered_urls)}] {len(all_map)} targets, {failed[0]} skipped", end="", flush=True)

    with ThreadPoolExecutor(max_workers=AGENT_WORKERS) as ex:
        futures = [ex.submit(_process, u) for u in filtered_urls]
        for f in as_completed(futures):
            f.result()

    print(f"\n\n=== {len(all_providers)} providers ===")
    if all_providers:
        dk.save(all_providers)
        print(f"Gespeichert: data/unchecked/{config.name}.json")

    # === STAGE 5: Geocoding ===
    print("\nStage 5: Geocoding ...")
    provider_dicts = [p.to_dict() if hasattr(p, "to_dict") else p for p in all_providers]
    geocoded = geocode_entries(provider_dicts, label="Geocoding")
    if geocoded > 0:
        import json
        dk._output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dk._output_path, "w", encoding="utf-8") as f:
            json.dump(provider_dicts, f, indent=2, ensure_ascii=False)
        print(f"  {geocoded} Einträge geocodiert und gespeichert")

    print("\nNaechste Schritte:")
    print("  python -m scraper.tools.clean")
    print("  python serve.py")
