"""Tests for the business profile, public profile endpoint and widget."""

from fastapi.testclient import TestClient

from app.core.business_profile import BusinessProfile, get_business_profile
from app.main import app

client = TestClient(app)


def test_example_profile_loads():
    profile = get_business_profile()
    assert profile.name
    assert profile.currency == "RM"


def test_knowledge_base_derives_prices_and_hours():
    profile = BusinessProfile(
        name="Test Salon",
        hours="Daily 10am-8pm",
        services=[{"name": "Haircut", "price": "RM 45"}],
        faq={"Parking": "Basement parking."},
    )
    kb = profile.knowledge_base()
    assert kb["hours"] == "Daily 10am-8pm"
    assert "RM 45" in kb["prices"]
    assert kb["parking"] == "Basement parking."


def test_whatsapp_link_optional():
    assert BusinessProfile().whatsapp_link() is None
    assert BusinessProfile(whatsapp="60123").whatsapp_link("hi there") == "https://wa.me/60123?text=hi%20there"


def test_public_profile_endpoint():
    res = client.get("/api/profile")
    assert res.status_code == 200
    data = res.json()
    assert data["name"]
    assert isinstance(data["services"], list)


def test_widget_js_served():
    res = client.get("/widget.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"]
    assert "/chat" in res.text
