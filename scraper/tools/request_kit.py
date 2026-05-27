"""
RequestKit — HTTP-Client mit Proxy, Rate-Limiting, Retry und ScrapingBee.

Ermöglicht Scrapern, Requests über einen Proxy oder ScrapingBee zu senden,
um IP-Sperren zu vermeiden, und das Request-Volumen zu kontrollieren.

ScrapingBee-Integration:
    Wenn SCRAPINGBEE_API_KEY in der .env gesetzt ist, werden alle Requests
    automatisch über ScrapingBee geroutet (headless browser, Rotating Proxies).
    Manuell steuerbar via use_scrapingbee=True/False im Konstruktor.

Proxy-Format (ohne ScrapingBee):
    http://user:pass@host:port
"""

import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

SCRAPINGBEE_API_KEY = os.environ.get("SCRAPINGBEE_API_KEY")


class RequestKit:
    """
    HTTP-Client für Scraper — wahlweise direkt oder über ScrapingBee.

    Usage:
        # Direkt (kein ScrapingBee):
        rk = RequestKit(rate=0.5, retries=3)

        # Mit eigenem Proxy:
        rk = RequestKit(proxy="http://user:pass@10.0.0.1:8080", rate=1.0)

        # Mit ScrapingBee (automatisch wenn .env gesetzt):
        rk = RequestKit(use_scrapingbee=True, rate=0.5)

        resp = rk.get("https://example.com/api/data")
    """

    def __init__(
        self,
        proxy: str | None = None,
        rate: float = 1.0,
        retries: int = 3,
        timeout: int = 30,
        use_scrapingbee: bool = False,
    ):
        """
        Args:
            proxy: Proxy-URL (z.B. "http://10.0.0.1:8080").
                   None = kein Proxy, direkte Verbindung.
                   Ignoriert wenn use_scrapingbee=True.
            rate: Minimale Sekunden zwischen Requests.
            retries: Anzahl Wiederholungen bei Server-Fehlern (5xx).
            timeout: Request-Timeout in Sekunden.
            use_scrapingbee: True = Request über ScrapingBee routen
                            (benötigt SCRAPINGBEE_API_KEY in .env).
        """
        self.session = requests.Session()
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

        self._sb_client = None
        if use_scrapingbee:
            from scrapingbee import ScrapingBeeClient

            api_key = SCRAPINGBEE_API_KEY
            if not api_key:
                raise ValueError(
                    "use_scrapingbee=True aber SCRAPINGBEE_API_KEY nicht in .env gesetzt"
                )
            self._sb_client = ScrapingBeeClient(api_key=api_key)

        self.rate = rate
        self.retries = retries
        self.timeout = timeout
        self._last_request = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        GET-Request mit Rate-Limiting und Retry.

        Args:
            url: Ziel-URL
            **kwargs: Werden an requests.Session.get() bzw.
                      ScrapingBeeClient.get() durchgereicht.

        Returns:
            Response-Objekt (status 2xx garantiert)
        """
        self._wait()
        params = kwargs.pop("params", None)
        base_timeout = kwargs.pop("timeout", self.timeout)

        if self._sb_client:
            return self._get_via_scrapingbee(url, params, base_timeout, **kwargs)
        return self._get_direct(url, params, base_timeout, **kwargs)

    def _get_direct(self, url, params, timeout, **kwargs) -> requests.Response:
        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(
                    url, params=params, timeout=timeout, **kwargs
                )
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                if e.response is not None and 400 <= e.response.status_code < 500:
                    raise
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)
            except requests.RequestException:
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)

        raise RuntimeError("unreachable")

    def _get_via_scrapingbee(self, url, params, timeout, **kwargs) -> requests.Response:
        resp = self._sb_client.get(
            url,
            params=params,
            retries=self.retries,
            timeout=timeout,
            **kwargs,
        )
        resp.raise_for_status()
        return resp

    def _wait(self) -> None:
        """Hält das Rate-Limit ein."""
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self.rate:
            time.sleep(self.rate - elapsed)
        self._last_request = time.monotonic()
