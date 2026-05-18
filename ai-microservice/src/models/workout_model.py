"""
Modèle ML de recommandation d'entraînement sportif.

Architecture :
  - Type d'entraînement : Gradient Boosting Classifier (GradientBoostingClassifier)
  - Intensité           : Decision Tree Classifier (pour l'explicabilité)
  - Durée               : Gradient Boosting Regressor

Cibles :
  workout_type  (classification – 6 classes)
  intensity     (classification – 3 niveaux)
  duration_min  (régression)

Features :
  âge, genre, poids, taille, IMC, objectif, niveau fitness,
  BPM moyen, durée moyenne, séances/semaine, équipement, blessures

Entraînement :
    python -m src.models.workout_model
"""

from __future__ import annotations

import logging
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    mean_absolute_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from src.config import settings
from src.data.generate_training_data import generate_workout_dataset

logger = logging.getLogger(__name__)

MODEL_VERSION = "1.0.0"
ARTIFACT_PATH = settings.MODEL_DIR / "workout_model.joblib"

FEATURE_COLS = [
    "age", "gender", "weight", "height", "bmi",
    "goal", "fitness_level", "avg_bpm", "avg_duration",
    "sessions_per_week", "has_equipment", "has_injuries",
]

WORKOUT_TYPE_LABELS = ["cardio", "strength", "hiit", "yoga", "flexibility", "mixed"]
INTENSITY_LABELS    = ["low", "moderate", "high"]


class WorkoutModel:
    """Encapsule l'entraînement, l'évaluation et l'inférence du modèle d'entraînement."""

    def __init__(self) -> None:
        self.type_pipeline:     Pipeline | None = None
        self.intensity_pipeline: Pipeline | None = None
        self.duration_pipeline:  Pipeline | None = None
        self.metrics: dict[str, Any] = {}
        self.version: str = MODEL_VERSION

    # ──────────────────────────── API publique ─────────────────────────────

    def load_or_train(self) -> None:
        if ARTIFACT_PATH.exists():
            logger.info("Chargement du modèle sportif depuis %s", ARTIFACT_PATH)
            artifact = joblib.load(ARTIFACT_PATH)
            self.type_pipeline      = artifact["type_pipeline"]
            self.intensity_pipeline = artifact["intensity_pipeline"]
            self.duration_pipeline  = artifact["duration_pipeline"]
            self.metrics            = artifact.get("metrics", {})
            self.version            = artifact.get("version", MODEL_VERSION)
        else:
            logger.info("Aucun artefact trouvé – entraînement du modèle sportif …")
            self.train()

    def train(self) -> dict[str, Any]:
        df = generate_workout_dataset()
        X  = df[FEATURE_COLS].values
        y_type     = df["workout_type"].values
        y_intensity = df["intensity"].values
        y_duration  = df["duration_min"].values

        X_tr, X_te, yt_tr, yt_te, yi_tr, yi_te, yd_tr, yd_te = train_test_split(
            X, y_type, y_intensity, y_duration, test_size=0.20, random_state=42
        )

        # ── Type d'entraînement : Gradient Boosting ──
        self.type_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("model",  GradientBoostingClassifier(
                n_estimators=150, max_depth=5, learning_rate=0.1,
                random_state=42,
            )),
        ])
        self.type_pipeline.fit(X_tr, yt_tr)

        # ── Intensité : Decision Tree (interprétable) ──
        self.intensity_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("model",  DecisionTreeClassifier(max_depth=6, random_state=42)),
        ])
        self.intensity_pipeline.fit(X_tr, yi_tr)

        # ── Durée : Gradient Boosting Regressor ──
        self.duration_pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("model",  GradientBoostingRegressor(
                n_estimators=150, max_depth=4, learning_rate=0.1,
                random_state=42,
            )),
        ])
        self.duration_pipeline.fit(X_tr, yd_tr)

        # ── Métriques ──
        yt_pred = self.type_pipeline.predict(X_te)
        yi_pred = self.intensity_pipeline.predict(X_te)
        yd_pred = self.duration_pipeline.predict(X_te)

        self.metrics = {
            "workout_type": {
                "accuracy": round(accuracy_score(yt_te, yt_pred), 4),
                "f1_weighted": round(
                    f1_score(yt_te, yt_pred, average="weighted"), 4
                ),
                "classification_report": classification_report(
                    yt_te, yt_pred,
                    target_names=WORKOUT_TYPE_LABELS,
                    output_dict=True,
                    zero_division=0,
                ),
            },
            "intensity": {
                "accuracy": round(accuracy_score(yi_te, yi_pred), 4),
                "f1_weighted": round(
                    f1_score(yi_te, yi_pred, average="weighted"), 4
                ),
                "classification_report": classification_report(
                    yi_te, yi_pred,
                    target_names=INTENSITY_LABELS,
                    output_dict=True,
                    zero_division=0,
                ),
            },
            "duration_min": {
                "MAE": round(mean_absolute_error(yd_te, yd_pred), 2),
                "R2":  round(r2_score(yd_te, yd_pred), 4),
            },
        }
        logger.info("Métriques sportif → type=%s  intensity=%s  duration=%s",
                    self.metrics["workout_type"]["accuracy"],
                    self.metrics["intensity"]["accuracy"],
                    self.metrics["duration_min"])

        joblib.dump(
            {
                "type_pipeline":      self.type_pipeline,
                "intensity_pipeline": self.intensity_pipeline,
                "duration_pipeline":  self.duration_pipeline,
                "metrics":            self.metrics,
                "version":            self.version,
            },
            ARTIFACT_PATH,
        )
        logger.info("Modèle sauvegardé : %s", ARTIFACT_PATH)
        return self.metrics

    def predict(
        self,
        age: int,
        gender: float,
        weight: float,
        height: float,
        goal: int,
        fitness_level: int,
        avg_bpm: float,
        avg_duration: float,
        sessions_per_week: int,
        has_equipment: int,
        has_injuries: int,
    ) -> dict[str, Any]:
        if any(p is None for p in [
            self.type_pipeline, self.intensity_pipeline, self.duration_pipeline
        ]):
            raise RuntimeError("Modèle non chargé – appelez load_or_train() d'abord.")

        bmi = weight / (height / 100) ** 2
        X   = np.array([[
            age, gender, weight, height, bmi,
            goal, fitness_level, avg_bpm, avg_duration,
            sessions_per_week, has_equipment, has_injuries,
        ]])

        wtype    = int(self.type_pipeline.predict(X)[0])
        intensity = int(self.intensity_pipeline.predict(X)[0])
        duration  = round(float(self.duration_pipeline.predict(X)[0]))

        return {
            "workout_type": WORKOUT_TYPE_LABELS[wtype],
            "intensity":    INTENSITY_LABELS[intensity],
            "duration_min": max(15, int(duration)),
        }


# ──────────────────────── Point d'entrée CLI ───────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    model = WorkoutModel()
    metrics = model.train()
    print("\n=== Métriques – Modèle Sportif ===")
    print(f"  Type      accuracy={metrics['workout_type']['accuracy']:.4f}  "
          f"F1={metrics['workout_type']['f1_weighted']:.4f}")
    print(f"  Intensité accuracy={metrics['intensity']['accuracy']:.4f}  "
          f"F1={metrics['intensity']['f1_weighted']:.4f}")
    print(f"  Durée     MAE={metrics['duration_min']['MAE']:.2f}  "
          f"R²={metrics['duration_min']['R2']:.4f}")
