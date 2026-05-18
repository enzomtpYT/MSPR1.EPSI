"""Tests du modèle et du service de recommandation nutritionnelle."""

from __future__ import annotations

import pytest

from src.models.nutrition_model import NutritionModel
from src.schemas.nutrition import NutritionRequest
from src.services.nutrition_service import get_nutrition_recommendation


# ──────────────────────── Tests du modèle ML ───────────────────────────────

class TestNutritionModel:
    def test_train_returns_metrics(self, nutrition_model: NutritionModel):
        assert nutrition_model.metrics, "Les métriques ne doivent pas être vides après entraînement."
        for col, m in nutrition_model.metrics.items():
            assert "MAE" in m and "R2" in m, f"Métriques manquantes pour {col}"

    def test_r2_above_threshold(self, nutrition_model: NutritionModel):
        for col, m in nutrition_model.metrics.items():
            assert m["R2"] > 0.85, (
                f"R² pour {col} trop faible : {m['R2']:.4f} (seuil 0.85)"
            )

    def test_predict_output_keys(self, nutrition_model: NutritionModel):
        result = nutrition_model.predict(
            age=30, gender=1.0, weight=75.0, height=175.0,
            goal=0, activity_level=1.55,
        )
        for key in ("calories", "protein_g", "carbs_g", "fat_g", "fiber_g"):
            assert key in result, f"Clé manquante : {key}"

    def test_predict_values_positive(self, nutrition_model: NutritionModel):
        result = nutrition_model.predict(
            age=25, gender=0.0, weight=60.0, height=165.0,
            goal=0, activity_level=1.375,
        )
        for key, val in result.items():
            assert val > 0, f"{key} devrait être positif, obtenu : {val}"

    def test_weight_loss_lower_calories_than_muscle_gain(
        self, nutrition_model: NutritionModel
    ):
        wl = nutrition_model.predict(30, 1.0, 80.0, 178.0, goal=0, activity_level=1.55)
        mg = nutrition_model.predict(30, 1.0, 80.0, 178.0, goal=1, activity_level=1.55)
        assert wl["calories"] < mg["calories"], (
            "Perte de poids devrait nécessiter moins de calories que prise de masse."
        )

    @pytest.mark.parametrize("age,weight,height,goal", [
        (18, 55.0, 162.0, 4),
        (45, 95.0, 182.0, 0),
        (65, 70.0, 170.0, 2),
    ])
    def test_predict_various_profiles(
        self, nutrition_model: NutritionModel, age, weight, height, goal
    ):
        result = nutrition_model.predict(
            age=age, gender=0.5, weight=weight, height=height,
            goal=goal, activity_level=1.55,
        )
        assert result["calories"] > 1000, "Calories trop basses pour un être humain."
        assert result["calories"] < 6000, "Calories trop élevées."


# ──────────────────────── Tests du service ─────────────────────────────────

class TestNutritionService:
    @pytest.mark.asyncio
    async def test_service_returns_response(
        self, nutrition_model, mock_pg_db, mock_mongo
    ):
        req = NutritionRequest(
            user_id=1,
            nb_meals_per_day=3,
            use_llm_enhancement=False,
        )
        response = await get_nutrition_recommendation(req, mock_pg_db, mock_mongo, nutrition_model)
        assert response.user_id == 1
        assert response.recommendation_id is not None
        assert response.macro_targets.calories > 0
        assert len(response.meal_plan) <= 3

    @pytest.mark.asyncio
    async def test_service_meal_plan_non_empty(
        self, nutrition_model, mock_pg_db, mock_mongo
    ):
        req = NutritionRequest(user_id=1, nb_meals_per_day=3)
        response = await get_nutrition_recommendation(req, mock_pg_db, mock_mongo, nutrition_model)
        assert len(response.meal_plan) > 0

    @pytest.mark.asyncio
    async def test_service_model_version_present(
        self, nutrition_model, mock_pg_db, mock_mongo
    ):
        req = NutritionRequest(user_id=1)
        response = await get_nutrition_recommendation(req, mock_pg_db, mock_mongo, nutrition_model)
        assert response.model_version == "1.0.0"

    @pytest.mark.asyncio
    async def test_service_mongo_insert_called(
        self, nutrition_model, mock_pg_db, mock_mongo
    ):
        req = NutritionRequest(user_id=1)
        await get_nutrition_recommendation(req, mock_pg_db, mock_mongo, nutrition_model)
        mock_mongo["nutrition_recommendations"].insert_one.assert_called_once()
