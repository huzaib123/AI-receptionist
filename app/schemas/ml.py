"""
Pydantic schemas for machine learning endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NoShowRequest(BaseModel):
    """Features required by the no-show risk prediction model."""

    age: int = Field(..., ge=0, description="Age of the customer.")
    days_until_appointment: int = Field(
        ..., ge=0, description="Days between booking/scheduling date and the appointment."
    )
    past_no_shows: int = Field(..., ge=0, description="Total number of prior no-shows for this customer.")
    appointment_hour: int = Field(..., ge=0, le=23, description="Hour of the appointment (0-23).")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of the week (0=Monday ... 6=Sunday).")


class NoShowResponse(BaseModel):
    """Response containing the probability and categorised risk level."""

    no_show_probability: float = Field(..., description="Predicted probability of no-show (0.0 to 1.0).")
    risk_level: str = Field(..., description="Risk level classification: 'low', 'medium', or 'high'.")
