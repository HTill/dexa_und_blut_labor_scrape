"""Shared Mistral AI low-level utilities.

Nur Ausfuehrung — keine Prompts, kein Provider-Bau.
Prompts und Provider-Logik gehoeren in den jeweiligen Scraper.
"""

import os
import re
import json

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MISTRAL_MODEL = "mistral-large-latest"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


def load_api_key() -> str:
    secrets_path = os.path.expanduser("~/.secrets/mistral-key")
    if os.path.exists(secrets_path):
        with open(secrets_path) as f:
            return f.read().strip()
    return os.getenv("MISTRAL_API_KEY", "")


def query_mistral(prompt: str, api_key: str) -> str:
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.post(
                MISTRAL_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MISTRAL_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4000,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 503:
                last_error = e
                import time
                time.sleep(2 ** attempt)
                continue
            raise
    raise last_error


def parse_json_response(content: str) -> list[dict]:
    for candidate in re.findall(r"\[.*\]", content, re.DOTALL):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```\w*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
        for candidate in re.findall(r"\[.*\]", content, re.DOTALL):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    print(f"  JSON parse failed: {content[:200]}")
    return []


def check_website(url: str) -> str:
    if not url or not url.startswith("http"):
        return "no_url"
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 404:
            return "dead_404"
        if resp.status_code >= 500:
            return "dead_5xx"
        return f"dead_{resp.status_code}"
    except requests.ConnectionError:
        return "dead_no_connection"
    except requests.Timeout:
        return "dead_timeout"
    except Exception:
        return "dead_unknown"


def filter_urls_by_snippet(results: list[dict], api_key: str) -> list[str]:
    """Ask Mistral to filter results using Brave's rich search data.
    
    Uses title, description, age, and extra_snippets from Brave to
    determine if a URL is likely a real lab/DEXA provider website.
    Returns list of URLs that pass the filter.
    """
    if not results:
        return []

    batched = [results[i:i+15] for i in range(0, len(results), 15)]
    kept: list[str] = []

    for batch in batched:
        snippets = []
        for i, r in enumerate(batch):
            extra_text = " ".join(r.get("extra_snippets", [])[:3])
            snippets.append({
                "idx": i,
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "description": r.get("description", ""),
                "age": r.get("age", ""),
                "extra_text": extra_text[:300],
            })

        prompt = f"""Du siehst Brave-Suchergebnisse mit Title, Description, URL und Extra-Text.
Entscheide fuer jedes Ergebnis: koennte das die Website einer ECHTEN medizinischen Einrichtung sein?

WICHTIG — Stage 3 ist NUR ein Grobfilter. Stage 4 (opencode Agent) besucht die Website spaeter und prueft den genauen Inhalt. Deine Aufgabe ist NUR, offensichtlichen Muell auszusortieren.

Echte medizinische Einrichtungen, die in Frage kommen koennten (keep: true):
- Labore, Arztpraxen, Radiologie-Zentren, MVZ, Kliniken, Krankenhaeuser
- Sportmedizin, Koerperanalyse-Studios, Fitness-Studios mit medizinischem Bezug
- Orthopaedie, Endokrinologie, Radiologie — auch wenn der Snippet nur Knochendichte erwaehnt
- JEDE Seite die nach einer konkreten Praxis/Klinik aussieht, selbst wenn der Snippet unvollstaendig wirkt
- Im Zweifel: keep: true (Stage 4 prueft genauer)

Keine echten Einrichtungen (keep: false):
- News-Artikel, Blogs, Foren, Wikipedia, Reddit
- Verzeichnisse (Jameda, Doctolib, Gelbe Seiten, Sanego)
- Shops, E-Commerce, Amazon
- Allgemeine Info-Seiten, Lexikon-Eintraege, Ratgeber (ohne konkreten Anbieter)
- SEO-Spam, Werbung, Affiliate-Seiten
- Hersteller-Websites fuer Medizingeraete
- Tierarzt, Veterinaermedizin

Ergebnisse:
{json.dumps(snippets, indent=2, ensure_ascii=False)}

Output NUR dieses JSON-Array:
[{{"idx": 0, "keep": true}}, {{"idx": 1, "keep": false, "reason": "News-Artikel"}}]"""

        try:
            content = query_mistral(prompt, api_key)
            parsed = parse_json_response(content)
            for item in parsed:
                idx = item.get("idx", -1)
                if item.get("keep") and 0 <= idx < len(batch):
                    kept.append(batch[idx].get("url", ""))
        except Exception:
            kept.extend(r.get("url", "") for r in batch if r.get("url"))

    return kept
