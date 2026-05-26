"""Tests für scraper/tools/request_kit.py"""

import time
from unittest.mock import patch, Mock

import pytest
import requests

from scraper.tools.request_kit import RequestKit


def test_request_kit_no_proxy():
    """RequestKit ohne Proxy sendet direkte Requests."""
    rk = RequestKit(rate=0)
    assert rk.session.proxies == {}


def test_request_kit_with_proxy():
    """RequestKit mit Proxy konfiguriert Session."""
    rk = RequestKit(proxy="http://10.0.0.1:8080")
    assert rk.session.proxies == {"http": "http://10.0.0.1:8080", "https": "http://10.0.0.1:8080"}


def test_rate_limiting():
    """Rate-Limiting verzögert Requests."""
    rk = RequestKit(rate=0.2)
    start = time.monotonic()
    rk._wait()
    mid1 = time.monotonic()
    rk._wait()
    mid2 = time.monotonic()
    # Erster _wait sofort (kein vorheriger Request), zweiter nach >= 0.2s
    assert mid1 - start < 0.1
    assert mid2 - mid1 >= 0.19


def test_retry_on_5xx():
    """Retry bei Server-Fehlern (5xx)."""
    fail1 = Mock(status_code=500, raise_for_status=Mock(side_effect=requests.HTTPError(response=Mock(status_code=500))))
    fail2 = Mock(status_code=503, raise_for_status=Mock(side_effect=requests.HTTPError(response=Mock(status_code=503))))
    ok_resp = Mock(status_code=200, raise_for_status=Mock())
    ok_resp.json.return_value = {"ok": True}

    rk = RequestKit(rate=0, retries=3)
    with patch.object(rk.session, "get", side_effect=[fail1, fail2, ok_resp]):
        resp = rk.get("http://example.com")
        assert resp.json() == {"ok": True}


def test_no_retry_on_4xx():
    """Kein Retry bei Client-Fehlern (4xx)."""
    fail = Mock(status_code=404, raise_for_status=Mock(side_effect=requests.HTTPError(response=Mock(status_code=404))))
    ok_resp = Mock(status_code=200, raise_for_status=Mock())

    rk = RequestKit(rate=0, retries=3)
    with patch.object(rk.session, "get", side_effect=[fail, ok_resp]) as mock_get:
        with pytest.raises(requests.HTTPError):
            rk.get("http://example.com")
        assert mock_get.call_count == 1


def test_params_passed_through():
    """GET-Parameter werden durchgereicht."""
    ok_resp = Mock(status_code=200, raise_for_status=Mock())
    rk = RequestKit(rate=0)
    with patch.object(rk.session, "get", return_value=ok_resp) as mock_get:
        rk.get("http://example.com", params={"key": "value"})
        mock_get.assert_called_once_with(
            "http://example.com", timeout=30, params={"key": "value"}
        )
