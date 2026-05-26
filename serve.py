#!/usr/bin/env python3
"""
Ein-Klick-Start: validiert und merged alle unchecked-Daten,
startet dann einen HTTP-Server für die Web-Karte.
"""

import http.server
import os
import socketserver
import sys
from pathlib import Path

PORT = 8000
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scraper.tools.clean import clean  # noqa: E402

os.chdir(HERE / "web")


def main() -> None:
    print("=== Clean & Validate ===")
    entries, errors = clean()

    if errors:
        print(f"⚠ {len(errors)} Validierungsfehler:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)

    print(f"✓ {len(entries)} verifizierte Einträge bereit")

    print(f"\n=== Karte unter http://localhost:{PORT} ===\n")

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer gestoppt.")


if __name__ == "__main__":
    main()
