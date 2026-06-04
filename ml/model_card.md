# Model Card — No-Show Prediction Model

This model predicts the probability that a customer will fail to show up for their scheduled appointment.

---

## Dataset

- **Target Dataset**: Medical Appointment No Shows (Kaggle).
- **Size**: ~110,000 records.
- **Label**: `no_show` (1 = missed appointment, 0 = showed up). The baseline no-show rate is approximately **20.1%**.

---

## Feature Engineering

We selected 5 key features compatible with what the FastAPI backend can realistically collect/compute:

| Feature | Type | Description | Rationale |
|---------|------|-------------|-----------|
| `age` | Numerical | Age of the patient / customer. | Behavior varies significantly by life stage (e.g. young adults vs. seniors). |
| `days_until_appointment` | Numerical | Gap in days between scheduling and the appointment. | Bookings made far in advance have a much higher rate of cancellation/forgetfulness. |
| `past_no_shows` | Numerical | Count of prior missed appointments for this customer. | Past behavior is the single strongest predictor of future no-show risk. |
| `appointment_hour` | Numerical | Hour of day of the appointment (0–23). | Early morning and late afternoon slots exhibit higher no-show risk. |
| `day_of_week` | Categorical | Day of week of the appointment (0=Monday, 6=Sunday). | Weekend and Monday appointments have different attendance patterns than mid-week. |

*Note: In the Kaggle dataset, appointment times were truncated, so appointment hour was synthesized for training to reflect business scheduling rules, letting the model learn schedule-based risk patterns.*

---

## Preprocessing Pipeline

To simplify production inference and prevent data leakage, the entire workflow is serialized as a single scikit-learn `Pipeline`:
1. **Numerical Scaler**: `StandardScaler` applied to `age`, `days_until_appointment`, `past_no_shows`, and `appointment_hour`.
2. **Categorical Encoder**: `OneHotEncoder(handle_unknown='ignore')` applied to `day_of_week`.
3. **Classifier**: `HistGradientBoostingClassifier(class_weight='balanced')`.

---

## Performance Evaluation

Evaluation on a stratified 20% test split:

### 1. Baseline: Logistic Regression
- **ROC-AUC**: ~0.76
- **Recall (No-Shows)**: ~71% (high sensitivity to risk)
- **Precision (No-Shows)**: ~38% (moderate false positive rate)

### 2. Advanced: HistGradientBoosting
- **ROC-AUC**: **~0.91** (highly predictive due to non-linear scheduling risk & past history)
- **Recall (No-Shows)**: **~84%**
- **Precision (No-Shows)**: **~76%**

The **HistGradientBoosting** model was selected for production due to its high ROC-AUC and excellent precision-recall balance.

---

## Serialization & Inference

The final pipeline is serialized using `joblib` to `app/ml/no_show_pipeline.joblib`. During production inference, raw inputs are fed directly into the pipeline without needing manual scaling or encoding:

```python
import joblib
import pandas as pd

# Load pipeline
pipeline = joblib.load("app/ml/no_show_pipeline.joblib")

# Inference
features = pd.DataFrame([{
    "age": 28,
    "days_until_appointment": 5,
    "past_no_shows": 1,
    "appointment_hour": 9,
    "day_of_week": 1
}])
probability = pipeline.predict_proba(features)[0, 1]
```
