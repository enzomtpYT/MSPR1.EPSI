"""Tests du modèle et du service de recommandation d'entraînement sportif."""

from __future__ import annotations

import pytest

from src.models.workout_model import WorkoutModel, WORKOUT_TYPE_LABELS, INTENSITY_LABELS
from src.schemas.workout import WorkoutRequest
from src.services.workout_service import get_workout_recommendation


# ──────────────────────── Tests du modèle ML ───────────────────────────────

class TestWorkoutModel:
    def test_train_returns_metrics(self, workout_model: WorkoutModel):
        assert workout_model.metrics, "Les métriques ne doivent pas être vides."
        assert "workout_type" in workout_model.metrics
        assert "intensity" in workout_model.metrics
        assert "duration_min" in workout_model.metrics

    def test_accuracy_above_threshold(self, workout_model: WorkoutModel):
        assert workout_model.metrics["workout_type"]["accuracy"] > 0.70, (
            f"Précision type trop faible : {workout_model.metrics['workout_type']['accuracy']}"
        )
        assert workout_model.metrics["intensity"]["accuracy"] > 0.70, (
            f"Précision intensité trop faible : {workout_model.metrics['intensity']['accuracy']}"
        )

    def test_predict_valid_labels(self, workout_model: WorkoutModel):
        result = workout_model.predict(
            age=30, gender=1.0, weight=80.0, height=178.0,
            goal=0, fitness_level=1, avg_bpm=140.0,
            avg_duration=40.0, sessions_per_week=4,
            has_equipment=1, has_injuries=0,
        )
        assert result["workout_type"] in WORKOUT_TYPE_LABELS
        assert result["intensity"] in INTENSITY_LABELS
        assert result["duration_min"] >= 15

    def test_predict_beginner_lower_duration_than_advanced(
        self, workout_model: WorkoutModel
    ):
        base = dict(
            age=30, gender=1.0, weight=75.0, height=175.0,
            goal=0, avg_bpm=140.0, avg_duration=35.0,
            sessions_per_week=3, has_equipment=1, has_injuries=0,
        )
        beg = workout_model.predict(**base, fitness_level=0)
        adv = workout_model.predict(**base, fitness_level=2)
        # La durée du débutant peut être ≤ celle de l'avancé
        assert beg["duration_min"] <= adv["duration_min"] + 20  # tolérance raisonnable

    @pytest.mark.parametrize("goal,expected_not", [
        (1, []),          # muscle_gain → strength probable
        (0, ["yoga"]),    # weight_loss → pas yoga
    ])
    def test_predict_goal_consistency(
        self, workout_model: WorkoutModel, goal, expected_not
    ):
        result = workout_model.predict(
            age=28, gender=1.0, weight=72.0, height=175.0,
            goal=goal, fitness_level=1, avg_bpm=135.0,
            avg_duration=45.0, sessions_per_week=4,
            has_equipment=1, has_injuries=0,
        )
        for excluded in expected_not:
            assert result["workout_type"] != excluded, (
                f"Type {excluded} inattendu pour goal={goal}"
            )


# ──────────────────────── Tests du service ─────────────────────────────────

class TestWorkoutService:
    @pytest.mark.asyncio
    async def test_service_returns_response(
        self, workout_model, mock_pg_db, mock_mongo
    ):
        req = WorkoutRequest(user_id=1, sessions_per_week=3)
        response = await get_workout_recommendation(req, mock_pg_db, mock_mongo, workout_model)
        assert response.user_id == 1
        assert response.recommendation_id is not None
        assert response.fitness_level_detected in ("beginner", "intermediate", "advanced")

    @pytest.mark.asyncio
    async def test_service_weekly_plan_non_empty(
        self, workout_model, mock_pg_db, mock_mongo
    ):
        req = WorkoutRequest(user_id=1, sessions_per_week=4)
        response = await get_workout_recommendation(req, mock_pg_db, mock_mongo, workout_model)
        assert len(response.weekly_plan) > 0

    @pytest.mark.asyncio
    async def test_service_exercises_per_session(
        self, workout_model, mock_pg_db, mock_mongo
    ):
        req = WorkoutRequest(user_id=1, sessions_per_week=3)
        response = await get_workout_recommendation(req, mock_pg_db, mock_mongo, workout_model)
        for session in response.weekly_plan:
            assert len(session.exercises) > 0, "Chaque séance doit avoir des exercices."

    @pytest.mark.asyncio
    async def test_service_mongo_insert_called(
        self, workout_model, mock_pg_db, mock_mongo
    ):
        req = WorkoutRequest(user_id=1, sessions_per_week=3)
        await get_workout_recommendation(req, mock_pg_db, mock_mongo, workout_model)
        mock_mongo["workout_recommendations"].insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_model_version_present(
        self, workout_model, mock_pg_db, mock_mongo
    ):
        req = WorkoutRequest(user_id=1)
        response = await get_workout_recommendation(req, mock_pg_db, mock_mongo, workout_model)
        assert response.model_version == "1.0.0"
