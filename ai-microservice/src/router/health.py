"""Router – Santé du service et métriques des modèles ML."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.config import settings

router = APIRouter()


@router.get("/health", summary="Vérification de l'état du service", tags=["Health"])
async def health_check() -> dict:
    return {"status": "ok", "service": "healthai-ai-microservice"}


@router.get("/models/metrics", summary="Métriques de performance des modèles ML", tags=["Health"])
async def model_metrics(request: Request) -> dict:
    """Retourne les métriques MAE / R² / F1 calculées lors de l'entraînement."""
    nutrition_model = getattr(request.app.state, "nutrition_model", None)
    workout_model   = getattr(request.app.state, "workout_model",   None)
    return {
        "nutrition_model": {
            "version": nutrition_model.version if nutrition_model else None,
            "metrics": nutrition_model.metrics if nutrition_model else {},
        },
        "workout_model": {
            "version": workout_model.version if workout_model else None,
            "metrics": workout_model.metrics if workout_model else {},
        },
    }


@router.post("/models/retrain", summary="Ré-entraîner les modèles ML", tags=["Health"])
async def retrain_models(request: Request) -> dict:
    """Déclenche un ré-entraînement complet des deux modèles (opération longue)."""
    nutrition_model = request.app.state.nutrition_model
    workout_model   = request.app.state.workout_model
    nut_metrics = nutrition_model.train()
    wkt_metrics = workout_model.train()
    return {
        "message": "Modèles ré-entraînés avec succès.",
        "nutrition_metrics": nut_metrics,
        "workout_metrics": wkt_metrics,
    }
