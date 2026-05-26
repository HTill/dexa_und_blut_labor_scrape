"""Services Enum — bekannte Leistungen für DEXA-Praxen und Blutlabore."""

from enum import StrEnum


class Service(StrEnum):
    DEXA_BODY_COMP = "DEXA Body Composition"
    DEXA_BONE_DENSITY = "DEXA Knochendichte"
    BLOOD_SELF_PAYER = "Bluttest Selbstzahler"
