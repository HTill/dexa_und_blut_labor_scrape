"""
RequestKit — HTTP-Client mit Proxy, Rate-Limiting und Retry.

Ermöglicht Scrapern, Requests über einen Proxy zu senden,
um IP-Sperren zu vermeiden, und das Request-Volumen zu kontrollieren.

Proxy-Format:
    http://user:pass@host:port
"""

import time

import requests


class RequestKit:
    """
    HTTP-Client für Scraper.

    Usage:
        rk = RequestKit(rate=0.5, retries=3)

        rk = RequestKit(proxy="http://user:pass@10.0.0.1:8080", rate=1.0)

        resp = rk.get("https://example.com/api/data")
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
            self.session.proxies = {"http": proxy, "https": proxy}

        self.rate = rate
        self.retries = retries
        self.timeout = timeout
        self._last_request = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        """
        GET-Request mit Rate-Limiting und Retry.

        Args:
            url: Ziel-URL
            **kwargs: Werden an requests.Session.get() durchgereicht.

        Returns:
            Response-Objekt (status 2xx garantiert)
        """
        self._wait()
        params = kwargs.pop("params", None)
        base_timeout = kwargs.pop("timeout", self.timeout)

        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(
                    url, params=params, timeout=base_timeout, **kwargs
                )
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                if e.response is not None and 400 <= e.response.status_code < 500:
                    if e.response.status_code != 429:
                        raise
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)
            except requests.RequestException:
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)

        raise RuntimeError("unreachable")

    def post(self, url: str, data: dict | None = None, **kwargs) -> requests.Response:
        self._wait()
        base_timeout = kwargs.pop("timeout", self.timeout)

        for attempt in range(self.retries + 1):
            try:
                resp = self.session.post(
                    url, data=data, timeout=base_timeout, **kwargs
                )
                resp.raise_for_status()
                return resp
            except requests.HTTPError as e:
                if e.response is not None and 400 <= e.response.status_code < 500:
                    if e.response.status_code != 429:
                        raise
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)
            except requests.RequestException:
                if attempt == self.retries:
                    raise
                time.sleep(2**attempt)

        raise RuntimeError("unreachable")

    def _wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self.rate:
            time.sleep(self.rate - elapsed)
        self._last_request = time.monotonic()
