"""
Tests for app/ml package and endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ml.no_show_model import predict_no_show_prob

client = TestClient(app)


def test_predict_no_show_prob_logic():
    """Verify predict_no_show_prob returns a valid probability."""
    # Low risk parameters (middle-aged, booked close to date, no past no-shows, mid-day hour)
    prob_low = predict_no_show_prob(
        age=45,
        days_until_appointment=0,
        past_no_shows=0,
        appointment_hour=12,
        day_of_week=2,
    )
    assert isinstance(prob_low, float)
    assert 0.0 <= prob_low <= 1.0

    # High risk parameters (many past no-shows, booked far in advance)
    prob_high = predict_no_show_prob(
        age=20,
        days_until_appointment=30,
        past_no_shows=5,
        appointment_hour=9,
        day_of_week=0,
    )
    assert isinstance(prob_high, float)
    assert 0.0 <= prob_high <= 1.0
    assert prob_high > prob_low


def test_endpoint_predict_success():
    """Test POST /ml/no_show returns 200 with expected structure."""
    payload = {
        "age": 30,
        "days_until_appointment": 5,
        "past_no_shows": 1,
        "appointment_hour": 14,
        "day_of_week": 1,
    }
    response = client.post("/ml/no_show", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "no_show_probability" in data
    assert "risk_level" in data
    assert isinstance(data["no_show_probability"], float)
    assert data["risk_level"] in ("low", "medium", "high")


def test_endpoint_predict_validation():
    """Test validation errors for invalid inputs on POST /ml/no_show."""
    # Invalid age (negative)
    payload_bad_age = {
        "age": -5,
        "days_until_appointment": 5,
        "past_no_shows": 1,
        "appointment_hour": 14,
        "day_of_week": 1,
    }
    response = client.post("/ml/no_show", json=payload_bad_age)
    assert response.status_code == 422

    # Invalid hour (> 23)
    payload_bad_hour = {
        "age": 30,
        "days_until_appointment": 5,
        "past_no_shows": 1,
        "appointment_hour": 25,
        "day_of_week": 1,
    }
    response = client.post("/ml/no_show", json=payload_bad_hour)
    assert response.status_code == 422

    # Invalid day_of_week (> 6)
    payload_bad_day = {
        "age": 30,
        "days_until_appointment": 5,
        "past_no_shows": 1,
        "appointment_hour": 14,
        "day_of_week": 7,
    }
    response = client.post("/ml/no_show", json=payload_bad_day)
    assert response.status_code == 422
