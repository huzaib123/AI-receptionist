"""
Production model loader and prediction wrapper for the no-show risk model.
"""

from __future__ import annotations

import os
import logging
import joblib
import pandas as pd

logger = logging.getLogger(__name__)

# Path to the serialized pipeline (located in the same directory)
PIPELINE_PATH = os.path.join(os.path.dirname(__file__), "no_show_pipeline.joblib")

_pipeline = None


def load_model() -> Any | None:
    """Lazy load the joblib model pipeline."""
    global _pipeline  # noqa: PLW0603
    if _pipeline is not None:
        return _pipeline

    if os.path.exists(PIPELINE_PATH):
        try:
            _pipeline = joblib.load(PIPELINE_PATH)
            logger.info("Successfully loaded ML no-show pipeline from %s", PIPELINE_PATH)
        except Exception:
            logger.exception("Failed to load ML no-show pipeline from %s", PIPELINE_PATH)
    else:
        logger.warning("ML no-show pipeline not found at %s. Falling back to heuristic.", PIPELINE_PATH)
    return _pipeline


def predict_no_show_prob(
    age: int,
    days_until_appointment: int,
    past_no_shows: int,
    appointment_hour: int,
    day_of_week: int,
) -> float:
    """
    Predict the probability that a patient will be a no-show.

    Input features:
        - age: patient age (>= 0)
        - days_until_appointment: difference in days between scheduled day and appointment day (>= 0)
        - past_no_shows: count of prior no-shows (>= 0)
        - appointment_hour: hour of day (e.g. 9-18)
        - day_of_week: 0 = Monday ... 6 = Sunday

    Returns:
        Probability of no-show (float between 0.0 and 1.0)
    """
    pipeline = load_model()
    if pipeline is not None:
        try:
            # Construct a DataFrame matching features expected by the training pipeline
            features_df = pd.DataFrame(
                [
                    {
                        "age": max(0, age),
                        "days_until_appointment": max(0, days_until_appointment),
                        "past_no_shows": max(0, past_no_shows),
                        "appointment_hour": appointment_hour,
                        "day_of_week": day_of_week,
                    }
                ]
            )
            prob = float(pipeline.predict_proba(features_df)[0, 1])
            return round(prob, 3)
        except Exception:
            logger.exception("ML prediction execution failed; falling back to heuristic.")

    # Fallback business rule heuristic (aligned with model patterns)
    base = 0.15
    if age < 30:
        base += 0.05
    base += min(0.40, past_no_shows * 0.15)
    base += min(0.20, days_until_appointment * 0.01)
    if appointment_hour < 10 or appointment_hour > 16:
        base += 0.08
    return round(min(1.0, max(0.0, base)), 3)
