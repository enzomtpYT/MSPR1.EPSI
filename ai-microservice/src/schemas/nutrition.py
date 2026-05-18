from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────── Entrée – profil utilisateur ───────────────────

GoalType = Literal[
    "weight_loss", "muscle_gain", "maintenance", "endurance", "general_health"
]
ActivityLevel = Literal["sedentary", "lightly_active", "moderately_active", "very_active"]


class NutritionRequest(BaseModel):
    user_id: int = Field(..., description="ID de l'utilisateur dans la DB principale")
    # Données optionnelles : si absent, récupéré depuis la DB
    age: Optional[int] = Field(None, ge=10, le=100)
    gender: Optional[Literal["male", "female", "other"]] = None
    weight_kg: Optional[float] = Field(None, gt=20, lt=300)
    height_cm: Optional[float] = Field(None, gt=100, lt=250)
    goal: Optional[GoalType] = None
    activity_level: Optional[ActivityLevel] = None
    allergies: Optional[str] = None
    dietary_preferences: Optional[str] = None
    budget_level: Optional[Literal["low", "medium", "high"]] = None
    nb_meals_per_day: int = Field(3, ge=1, le=6)
    use_llm_enhancement: bool = Field(
        False, description="Enrichir la réponse via le LLM (Ollama/HuggingFace)"
    )


# ──────────────────────────── Sortie – recommandation ──────────────────────

class MacroTargets(BaseModel):
    calories: float = Field(..., description="Calories journalières recommandées (kcal)")
    protein_g: float = Field(..., description="Protéines recommandées (g)")
    carbs_g: float = Field(..., description="Glucides recommandés (g)")
    fat_g: float = Field(..., description="Lipides recommandés (g)")
    fiber_g: float


class MealPlanItem(BaseModel):
    meal_slot: str = Field(..., description="Ex: petit-déjeuner, déjeuner, dîner, collation")
    product_id: Optional[int] = None
    product_name: str
    portion_g: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class NutritionResponse(BaseModel):
    user_id: int
    recommendation_id: str = Field(..., description="ID MongoDB de la recommandation")
    macro_targets: MacroTargets
    meal_plan: list[MealPlanItem]
    deficit_warnings: list[str] = Field(default_factory=list)
    excess_warnings: list[str] = Field(default_factory=list)
    llm_advice: Optional[str] = None
    model_version: str
    generated_at: datetime


# ──────────────────────── Historique des recommandations ───────────────────

class NutritionRecommendationRecord(BaseModel):
    recommendation_id: str
    user_id: int
    macro_targets: MacroTargets
    meal_plan: list[MealPlanItem]
    model_version: str
    generated_at: datetime
