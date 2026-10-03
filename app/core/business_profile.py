"""
Per-business profile — the one file that turns the generic receptionist
into a branded receptionist for a specific client.

Loaded from the JSON file at ``BUSINESS_PROFILE_FILE`` (defaults to
``config/business_profile.json``, falling back to the bundled example).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.core.settings import settings

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parents[2]
_EXAMPLE_PATH = _ROOT / "config" / "business_profile.example.json"


class Service(BaseModel):
    name: str
    price: str = ""
    duration_min: int = 60


class BusinessProfile(BaseModel):
    name: str = "Our Business"
    industry: str = "service business"
    tagline: str = ""
    address: str = ""
    phone: str = ""
    whatsapp: str = Field("", description="WhatsApp number in international format, digits only.")
    email: str = ""
    timezone: str = "Asia/Kuala_Lumpur"
    currency: str = "RM"
    languages: list[str] = Field(default_factory=lambda: ["English"])
    brand_color: str = "#0f766e"
    hours: str = ""
    services: list[Service] = Field(default_factory=list)
    faq: dict[str, str] = Field(default_factory=dict)

    def whatsapp_link(self, text: str = "") -> Optional[str]:
        if not self.whatsapp:
            return None
        from urllib.parse import quote

        link = f"https://wa.me/{self.whatsapp}"
        return f"{link}?text={quote(text)}" if text else link

    def knowledge_base(self) -> dict[str, str]:
        """FAQ entries plus answers derived from the structured fields."""
        kb: dict[str, str] = {}
        if self.hours:
            kb["hours"] = kb["opening hours"] = self.hours
        if self.address:
            kb["address"] = kb["location"] = f"We are located at {self.address}."
        if self.services:
            menu = " | ".join(
                f"{s.name}: {s.price}" if s.price else s.name for s in self.services
            )
            kb["services"] = kb["price"] = kb["prices"] = menu
        contact = ", ".join(
            p for p in [self.phone, f"WhatsApp {self.whatsapp_link()}" if self.whatsapp else "", self.email] if p
        )
        if contact:
            kb["contact"] = kb["phone"] = f"You can reach us at {contact}."
        # Explicit FAQ entries win over derived ones.
        kb.update({k.lower(): v for k, v in self.faq.items()})
        return kb


@lru_cache(maxsize=1)
def get_business_profile() -> BusinessProfile:
    path = Path(settings.BUSINESS_PROFILE_FILE)
    if not path.is_absolute():
        path = _ROOT / path
    if not path.exists():
        logger.warning("Business profile %s not found; using bundled example.", path)
        path = _EXAMPLE_PATH
    return BusinessProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))
