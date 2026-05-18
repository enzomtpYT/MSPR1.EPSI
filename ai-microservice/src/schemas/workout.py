from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────── Types communs ─────────────────────────────────

WorkoutType = Literal["cardio", "strength", "hiit", "yoga", "flexibility", "mixed"]
IntensityLevel = Literal["low", "moderate", "high"]
FitnessLevel = Literal["beginner", "intermediate", "advanced"]


# ─────────────────────────── Entrée ────────────────────────────────────────

class WorkoutRequest(BaseModel):
    user_id: int = Field(..., description="ID de l'utilisateur dans la DB principale")
    # Données optionnelles : si absent, récupéré depuis la DB
    age: Optional[int] = Field(None, ge=10, le=100)
    gender: Optional[Literal["male", "female", "other"]] = None
    weight_kg: Optional[float] = Field(None, gt=20, lt=300)
    height_cm: Optional[float] = Field(None, gt=100, lt=250)
    goal: Optional[
        Literal["weight_loss", "muscle_gain", "maintenance", "endurance", "general_health"]
    ] = None
    available_equipment: Optional[list[str]] = Field(
        default_factory=list,
        description="Equipements disponibles (ex: ['barbell', 'treadmill'])",
    )
    injuries: Optional[str] = None
    preferred_duration_min: Optional[int] = Field(None, ge=10, le=180)
    sessions_per_week: int = Field(3, ge=1, le=7)
    use_llm_enhancement: bool = Field(False)


# ─────────────────────────── Sortie ────────────────────────────────────────

class ExerciseItem(BaseModel):
    name: str
    sets: Optional[int] = None
    reps: Optional[str] = None      # "8-12" ou "30 secondes"
    rest_seconds: Optional[int] = None
    kcal_burned_estimate: Optional[float] = None
    notes: Optional[str] = None


class WorkoutSession(BaseModel):
    day: int = Field(..., description="Numéro du jour dans la semaine (1–7)")
    workout_type: WorkoutType
    intensity: IntensityLevel
    duration_min: int
    exercises: list[ExerciseItem]
    warm_up: list[str] = Field(default_factory=list)
    cool_down: list[str] = Field(default_factory=list)


class WorkoutResponse(BaseModel):
    user_id: int
    recommendation_id: str
    fitness_level_detected: FitnessLevel
    weekly_plan: list[WorkoutSession]
    adaptive_notes: list[str] = Field(default_factory=list)
    contraindications: list[str] = Field(default_factory=list)
    llm_advice: Optional[str] = None
    model_version: str
    generated_at: datetime


# ──────────────────────── Historique ───────────────────────────────────────

class WorkoutRecommendationRecord(BaseModel):
    recommendation_id: str
    user_id: int
    fitness_level_detected: FitnessLevel
    weekly_plan: list[WorkoutSession]
    model_version: str
    generated_at: datetime
