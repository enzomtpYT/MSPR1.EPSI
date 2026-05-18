"""Router – Recommandations nutritionnelles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.orm import Session

from src.database import get_mongo, get_pg_db
from src.schemas.nutrition import NutritionRequest, NutritionResponse
from src.services.nutrition_service import get_nutrition_recommendation

router = APIRouter()


@router.post(
    "/recommend",
    response_model=NutritionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Générer une recommandation nutritionnelle personnalisée",
    description=(
        "Prédit les besoins caloriques et macronutritionnels d'un utilisateur "
        "à partir de son profil, puis construit un plan de repas adapté à ses "
        "contraintes (allergies, budget, régime). "
        "Enrichissement LLM optionnel via `use_llm_enhancement=true`."
    ),
)
async def create_nutrition_recommendation(
    body: NutritionRequest,
    request: Request,
    db: Session = Depends(get_pg_db),
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
) -> NutritionResponse:
    nutrition_model = request.app.state.nutrition_model
    try:
        return await get_nutrition_recommendation(body, db, mongo, nutrition_model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur interne : {exc}") from exc


@router.get(
    "/history/{user_id}",
    summary="Historique des recommandations nutritionnelles",
    description="Retourne les 20 dernières recommandations stockées dans MongoDB pour un utilisateur.",
)
async def get_nutrition_history(
    user_id: int,
    mongo: AsyncIOMotorDatabase = Depends(get_mongo),
    limit: int = 20,
) -> list[dict]:
    cursor = (
        mongo["nutrition_recommendations"]
        .find({"user_id": user_id}, {"_id": 1, "macro_targets": 1, "generated_at": 1})
        .sort("generated_at", -1)
        .limit(max(1, min(limit, 100)))
    )
    return [doc async for doc in cursor]
