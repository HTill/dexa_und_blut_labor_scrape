"""Extrahiert Preise aus der Synlab Privattarife-PDF.

Usage:
    python -m scraper.scrapers.synlab.extract_prices
    Oder direkt: python scraper/scrapers/synlab/extract_prices.py

Lädt die PDF von synlab.at, extrahiert Preise mit pdftotext,
und speichert sie als data/unchecked/synlab_prices.json.
"""

if __name__ == "__main__" and __package__ is None:
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import json
import re
import subprocess
import tempfile
from pathlib import Path

import requests

PDF_URL = "https://www.synlab.at/wp-content/uploads/2026/01/Privattarife-Januar-2026.pdf"
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "unchecked" / "synlab_prices.json"


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extrahiert Text aus PDF mit pdftotext."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        tmp_pdf.write(pdf_bytes)
        tmp_pdf.flush()
        result = subprocess.run(
            ["pdftotext", "-layout", tmp_pdf.name, "-"],
            capture_output=True,
            text=True,
        )
        Path(tmp_pdf.name).unlink(missing_ok=True)
        return result.stdout


def parse_prices(text: str) -> list[dict]:
    """Parst die Preistabelle aus dem PDF-Text."""
    prices = []
    # Reguläre Einträge: ID  Name  Preis
    # Zeilenformat: "LEISTUNGSID  Name  Preis" wobei Preis eine Zahl mit Komma ist
    line_regex = re.compile(r"^([A-Z0-9]{3,10})\s{2,}(.+?)\s{2,}(\d{1,3}(?:,\d{2}))\s*$")

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = line_regex.match(line)
        if match:
            test_id = match.group(1)
            name = match.group(2).strip()
            price_str = match.group(3).replace(",", ".")
            try:
                price = float(price_str)
                prices.append({
                    "id": test_id,
                    "name": name,
                    "price_eur": price,
                })
            except ValueError:
                continue

    return prices


def main() -> None:
    print(f"=== Synlab Preisliste: {PDF_URL} ===\n")

    resp = requests.get(PDF_URL, timeout=30)
    resp.raise_for_status()
    print(f"PDF geladen: {len(resp.content)} bytes")

    text = extract_text_from_pdf(resp.content)
    prices = parse_prices(text)

    print(f"Preise extrahiert: {len(prices)} Einträge")

    if prices:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "source": PDF_URL,
                "note": "Preise aus AT-PDF (exkl. 10% MWST), Stand Januar 2026",
                "prices": prices,
            }, f, indent=2, ensure_ascii=False)
        print(f"Gespeichert: {OUTPUT_PATH}")

        # Preview
        for p in prices[:5]:
            print(f"  {p['id']}: {p['name']} = {p['price_eur']:.2f} €")
    else:
        print("Keine Preise gefunden!")


if __name__ == "__main__":
    main()
