"""
Modèle ML de recommandation nutritionnelle.

Architecture : Random Forest multi-sorties (MultiOutputRegressor)
Cibles       : calories, protéines, glucides, lipides, fibres
Features     : âge, genre, poids, taille, IMC, objectif, niveau d'activité

Entraînement :
    python -m src.models.nutrition_model
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import settings
from src.data.generate_training_data import generate_nutrition_dataset

logger = logging.getLogger(__name__)

MODEL_VERSION = "1.0.0"
ARTIFACT_PATH = settings.MODEL_DIR / "nutrition_model.joblib"

FEATURE_COLS = ["age", "gender", "weight", "height", "bmi", "goal", "activity_level"]
TARGET_COLS  = [
    "target_calories", "target_protein", "target_carbs",
    "target_fat", "target_fiber",
]


class NutritionModel:
    """Encapsule l'entraînement, l'évaluation et l'inférence du modèle nutritionnel."""

    def __init__(self) -> None:
        self.pipeline: Pipeline | None = None
        self.metrics: dict[str, Any] = {}
        self.version: str = MODEL_VERSION

    # ──────────────────────────── API publique ─────────────────────────────

    def load_or_train(self) -> None:
        """Charge le modèle depuis le disque ou l'entraîne si absent."""
        if ARTIFACT_PATH.exists():
            logger.info("Chargement du modèle nutritionnel depuis %s", ARTIFACT_PATH)
            artifact = joblib.load(ARTIFACT_PATH)
            self.pipeline = artifact["pipeline"]
            self.metrics  = artifact.get("metrics", {})
            self.version   = artifact.get("version", MODEL_VERSION)
        else:
            logger.info("Aucun artefact trouvé – entraînement du modèle nutritionnel …")
            self.train()

    def train(self) -> dict[str, Any]:
        """Entraîne le modèle, calcule les métriques et sauvegarde l'artefact."""
        df = generate_nutrition_dataset()
        X  = df[FEATURE_COLS].values
        y  = df[TARGET_COLS].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42
        )

        base_rf = RandomForestRegressor(random_state=42, n_jobs=-1)
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("model",  MultiOutputRegressor(base_rf)),
        ])

        # Recherche d'hyperparamètres légère (compatible temps de MSPR)
        param_grid = {
            "model__estimator__n_estimators": [100, 200],
            "model__estimator__max_depth":    [None, 15],
        }
        grid_search = GridSearchCV(
            pipeline, param_grid, cv=3, scoring="r2",
            n_jobs=-1, verbose=0,
        )
        grid_search.fit(X_train, y_train)

        self.pipeline = grid_search.best_estimator_
        y_pred = self.pipeline.predict(X_test)

        self.metrics = self._compute_metrics(y_test, y_pred)
        logger.info("Métriques nutrition → %s", self.metrics)

        joblib.dump(
            {"pipeline": self.pipeline, "metrics": self.metrics, "version": self.version},
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
        activity_level: float,
    ) -> dict[str, float]:
        """Retourne les cibles nutritionnelles pour un profil utilisateur."""
        if self.pipeline is None:
            raise RuntimeError("Modèle non chargé – appelez load_or_train() d'abord.")

        bmi = weight / (height / 100) ** 2
        X   = np.array([[age, gender, weight, height, bmi, goal, activity_level]])
        y   = self.pipeline.predict(X)[0]

        return {
            "calories": round(float(y[0]), 1),
            "protein_g": round(float(y[1]), 1),
            "carbs_g":   round(float(y[2]), 1),
            "fat_g":     round(float(y[3]), 1),
            "fiber_g":   round(float(y[4]), 1),
        }

    # ──────────────────────── Métriques ────────────────────────────────────

    @staticmethod
    def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        for idx, col in enumerate(TARGET_COLS):
            mae = mean_absolute_error(y_true[:, idx], y_pred[:, idx])
            r2  = r2_score(y_true[:, idx], y_pred[:, idx])
            metrics[col] = {"MAE": round(mae, 3), "R2": round(r2, 4)}
        return metrics


# ──────────────────────── Point d'entrée CLI ───────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    model = NutritionModel()
    metrics = model.train()
    print("\n=== Métriques – Modèle Nutritionnel ===")
    for target, m in metrics.items():
        print(f"  {target:20s}  MAE={m['MAE']:8.2f}  R²={m['R2']:.4f}")
