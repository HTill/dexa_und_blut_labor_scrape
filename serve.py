#!/usr/bin/env python3
"""
HTTP-Server fuer die Web-Karte.

Nur Serving — kein Clean/Validate.
clean.py separat ausfuehren vor dem Starten.
"""

import http.server
import os
import socketserver
from pathlib import Path

PORT = 8000
HERE = Path(__file__).resolve().parent

os.chdir(HERE / "web")

data_link = HERE / "web" / "data"
if not data_link.exists():
    data_link.symlink_to(HERE / "data", target_is_directory=True)


def main() -> None:
    print(f"=== Karte unter http://localhost:{PORT} ===\n")
    print("Vor dem Start ausfuehren: python -m scraper.tools.clean\n")

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer gestoppt.")


if __name__ == "__main__":
    main()
