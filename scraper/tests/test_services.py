"""Tests für scraper/tools/services.py"""

import json

from scraper.tools.services import Service
from scraper.tools.models import Provider, Address, Coordinates


def test_service_values():
    """Enum-Werte sind Strings."""
    assert isinstance(Service.DEXA_BODY_COMP, str)
    assert Service.DEXA_BODY_COMP == "DEXA Body Composition"
    assert Service.DEXA_BONE_DENSITY == "DEXA Knochendichte"
    assert Service.BLOOD_SELF_PAYER == "Bluttest Selbstzahler"


def test_service_serializable():
    """Enum-Werte sind JSON-serialisierbar."""
    services = [Service.DEXA_BODY_COMP, Service.BLOOD_SELF_PAYER]
    assert json.dumps(services) == json.dumps(["DEXA Body Composition", "Bluttest Selbstzahler"])


def test_service_in_provider():
    """Enum-Werte im Provider-Model."""
    p = Provider(
        id="test",
        name="Test",
        category="beide",
        address=Address(street="s", postal_code="p", city="c", country="DE"),
        coordinates=Coordinates(lat=0, lng=0),
        services=[Service.DEXA_BODY_COMP, Service.BLOOD_SELF_PAYER],
    )
    d = p.to_dict()
    assert d["services"] == ["DEXA Body Composition", "Bluttest Selbstzahler"]


def test_all_services_unique():
    """Keine Duplikate in den Enum-Werten."""
    values = list(Service)
    assert len(values) == len(set(values))
