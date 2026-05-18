"""Router – Recommandations d'entraînement sportif."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.orm import Session

from src.database import get_mongo, get_pg_db
from src.schemas.workout import WorkoutRequest, WorkoutResponse
from src.services.workout_service import get_workout_recommendation

router = APIRouter()


@router.post(
    "/recommend",
    response_model=WorkoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer un programme d'entraînement personnalisé",
    description=(
        "Détermine le niveau de forme de l'utilisateur à partir de son "
        "historique de sessions, puis génère un plan hebdomadaire adapté "
        "à son objectif, son équipement et ses éventuelles blessures. "
        "Enrichissement LLM optionnel via `use_llm_enhancement=true`."
    ),
)
async def create_workout_recommendation(
    body: WorkoutRequest,
    request: Request,
    db: Session = Depends(get_pg_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
) -> WorkoutResponse:
    workout_model = request.app.state.workout_model
    try:
        return await get_workout_recommendation(body, db, mongo, workout_model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur interne : {exc}") from exc


@router.get(
    "/history/{user_id}",
    summary="Historique des programmes d'entraînement",
    description="Retourne les 20 derniers programmes stockés dans MongoDB pour un utilisateur.",
)
async def get_workout_history(
    user_id: int,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    limit: int = 20,
) -> list[dict]:
    cursor = (
        mongo["workout_recommendations"]
        .find(
            {"user_id": user_id},
            {"_id": 1, "fitness_level": 1, "model_version": 1, "generated_at": 1},
        )
        .sort("generated_at", -1)
        .limit(max(1, min(limit, 100)))
    )
    return [doc async for doc in cursor]
