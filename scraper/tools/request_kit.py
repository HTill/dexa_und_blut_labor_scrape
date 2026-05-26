"""
RequestKit — HTTP-Client mit Proxy, Rate-Limiting und Retry.

Ermöglicht Scrapern, Requests über einen Proxy zu senden,
um IP-Sperren zu vermeiden, und das Request-Volumen zu kontrollieren.
"""

import time
from urllib.parse import urlparse

import requests


class RequestKit:
    """
    HTTP-Client für Scraper.

    Usage:
        rk = RequestKit(proxy="http://user:pass@10.0.0.1:8080", rate=1.0, retries=3)
        resp = rk.get("https://example.com/api/data")

    Proxy-Einrichtung mit nginx (auf eigenem Server):
        server {
            listen 8080;
            location / {
                resolver 8.8.8.8;
                proxy_pass $scheme://$host$request_uri;
                proxy_set_header Host $host;
            }
        }
    """

    def __init__(
        self,
        proxy: str | None = None,
        rate: float = 1.0,
        retries: int = 3,
        timeout: int = 30,
    ):
        """
        Args:
            proxy: Proxy-URL (z.B. "http://10.0.0.1:8080").
                   None = kein Proxy, direkte Verbindung.
            rate: Minimale Sekunden zwischen Requests.
            retries: Anzahl Wiederholungen bei Server-Fehlern (5xx).
            timeout: Request-Timeout in Sekunden.
        """
        self.session = requests.Session()
        if proxy:
            self.session.proxies = {
                "http": proxy,
                "https": proxy,
            }
        self.rate = rate
        self.retries = retries
        self.timeout = timeout
        self._last_request = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        GET-Request mit Rate-Limiting und Retry.

        Args:
            url: Ziel-URL
            **kwargs: Werden an requests.Session.get() durchgereicht

        Returns:
            Response-Objekt (status 2xx garantiert)
        """
        self._wait()
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, timeout=kwargs.pop("timeout", self.timeout), **kwargs)
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                if e.response is not None and 400 <= e.response.status_code < 500:
                    raise  # Kein Retry bei Client-Fehlern (4xx)
                if attempt == self.retries:
                    raise
                time.sleep(2 ** attempt)
            except requests.RequestException:
                if attempt == self.retries:
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError("unreachable")

    def _wait(self) -> None:
        """Hält das Rate-Limit ein."""
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self.rate:
            time.sleep(self.rate - elapsed)
        self._last_request = time.monotonic()
