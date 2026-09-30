"""
Flask backend for the MathE Learning Outcomes Prediction project.

Folder structure this file expects (adjust MODEL_DIR below if yours differs):

    project_root/
        app.py                  <- this file
        templates/
            index.html
        model/
            best_model.pkl
            feature_columns.json
            thresholds.json

Run with:
    python app.py
Then open http://127.0.0.1:5000 in your browser.
"""

from pathlib import Path
import json

import joblib
import pandas as pd
from flask import Flask, render_template, request

app = Flask(__name__)

# ---------------------------------------------------------------------
# Load the trained model + supporting files (loaded once at startup)
# ---------------------------------------------------------------------
MODEL_DIR = Path("model")

model = joblib.load(MODEL_DIR / "best_model.pkl")

with open(MODEL_DIR / "feature_columns.json", "r", encoding="utf-8") as f:
    FEATURE_COLUMNS = json.load(f)

with open(MODEL_DIR / "thresholds.json", "r", encoding="utf-8") as f:
    THRESHOLDS = json.load(f)

# Topics are displayed in the form, but individual topic counts
# are NOT used directly by the current ML model.
TOPICS = [
    "Analytic Geometry",
    "Complex Numbers",
    "Differential Equations",
    "Differentiation",
    "Fundamental Mathematics",
    "Graph Theory",
    "Integration",
    "Linear Algebra",
    "Numerical Methods",
    "Optimization",
    "Probability",
    "Real Functions of a single variable",
    "Set Theory",
    "Statistics",
]

TOPIC_LABELS = [
    (f"topic_{topic}", topic)
    for topic in TOPICS
]

COUNTRY_COLUMNS = [
    c for c in FEATURE_COLUMNS
    if c.startswith("country_")
]

COUNTRY_LABELS = [
    (c, c.replace("country_", "").replace("_", " "))
    for c in COUNTRY_COLUMNS
]


def accuracy_to_label(accuracy_percent: float) -> str:
    """Bucket a raw accuracy percentage into LOW / MEDIUM / HIGH,
    using the same thresholds saved by the notebook."""
    if accuracy_percent < THRESHOLDS["low_max"]:
        return "LOW"
    elif accuracy_percent < THRESHOLDS["medium_max"]:
        return "MEDIUM"
    else:
        return "HIGH"


@app.route("/", methods=["GET"])
def index():
    """Show the empty input form."""
    return render_template(
        "index.html",
        topics=TOPIC_LABELS,
        countries=COUNTRY_LABELS,
        result=None,
    )


@app.route("/predict", methods=["POST"])
def predict():
    """Read the form, build the feature vector, run the model,
    and render the assessment box with both the raw stats and
    the ML-predicted outcome."""

    form = request.form

    student_id = form.get("student_id", "").strip() or "N/A"
    selected_country = form.get("country")

    basic_total = int(form.get("basic_total") or 0)
    basic_correct = int(form.get("basic_correct") or 0)
    advanced_total = int(form.get("advanced_total") or 0)
    advanced_correct = int(form.get("advanced_correct") or 0)

    if basic_correct > basic_total:
        return "Basic correct answers cannot exceed basic questions.", 400

    if advanced_correct > advanced_total:
        return "Advanced correct answers cannot exceed advanced questions.", 400

    # --- Values shown directly on the assessment card (plain arithmetic,
    #     NOT model output) -------------------------------------------------
    total_questions = basic_total + advanced_total
    correct_answers = basic_correct + advanced_correct
    overall_accuracy = (correct_answers / total_questions * 100) if total_questions else 0.0
    basic_accuracy = (basic_correct / basic_total * 100) if basic_total else None
    advanced_accuracy = (advanced_correct / advanced_total * 100) if advanced_total else None

    # --- Build the feature row the model expects ---------------------------
    row = {col: 0 for col in FEATURE_COLUMNS}
    row = pd.DataFrame([row]).astype(object)

    row.loc[0, "total_questions"] = total_questions

    row.loc[0, "basic_ratio"] = (
        basic_total / total_questions if total_questions else 0
    )

    row.loc[0, "advanced_ratio"] = (
        advanced_total / total_questions if total_questions else 0
    )
    topics_attempted = 0

    for col, label in TOPIC_LABELS:
        count = int(form.get(f"topic__{col}") or 0)

        if count > 0:
            topics_attempted += 1

    row.loc[0, "unique_topics"] = topics_attempted

    country_col = f"country_{selected_country}"
    if country_col in COUNTRY_COLUMNS:
        row.loc[0, country_col] = True

    # --- Run the model -------------------------------------------------
    predicted_accuracy = float(model.predict(row[FEATURE_COLUMNS])[0])

    # Current performance based on the student's actual answers
    current_label = accuracy_to_label(overall_accuracy)

    # ML prediction based on question-attempt patterns
    predicted_label = accuracy_to_label(predicted_accuracy)

    result = {
        "student_id": student_id,
        "questions_answered": total_questions,
        "correct_answers": correct_answers,
        "accuracy": round(overall_accuracy, 1),
        "basic_accuracy": round(basic_accuracy, 1) if basic_accuracy is not None else None,
        "advanced_accuracy": round(advanced_accuracy, 1) if advanced_accuracy is not None else None,
        "current_label": current_label,
        "predicted_accuracy": round(predicted_accuracy, 1),
        "predicted_label": predicted_label,
    }

    return render_template(
        "index.html",
        topics=TOPIC_LABELS,
        countries=COUNTRY_LABELS,
        result=result,
    )


if __name__ == "__main__":
    app.run(debug=True)