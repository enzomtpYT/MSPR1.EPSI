"""
Service métier – Recommandations d'entraînement sportif.

Orchestration :
 1. Lecture profil utilisateur (PostgreSQL)
 2. Calcul du niveau de forme depuis l'historique des sessions
 3. Prédiction du programme via le modèle ML
 4. Construction du plan hebdomadaire détaillé
 5. Gestion des contre-indications (blessures)
 6. Enrichissement optionnel via LLM
 7. Persistance MongoDB
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.orm import Session

from src.models.workout_model import WorkoutModel
from src.schemas.workout import (
    ExerciseItem,
    WorkoutRequest,
    WorkoutResponse,
    WorkoutSession as WorkoutSessionSchema,
)
from src.services.llm_service import enhance_workout_recommendation

logger = logging.getLogger(__name__)

GOAL_MAP     = {
    "weight_loss": 0, "muscle_gain": 1, "maintenance": 2,
    "endurance": 3, "general_health": 4,
}
FITNESS_MAP  = {"beginner": 0, "intermediate": 1, "advanced": 2}
GENDER_MAP   = {"female": 0.0, "male": 1.0, "other": 0.5}


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


# ──────────────────────── Lecture DB ───────────────────────────────────────

def _fetch_user(user_id: int, db: Session) -> dict:
    from sqlalchemy import text
    row = db.execute(
        text('SELECT * FROM users WHERE "User_ID" = :uid'), {"uid": user_id}
    ).mappings().first()
    if row is None:
        raise ValueError(f"Utilisateur {user_id} introuvable.")
    return dict(row)


def _fetch_workout_stats(user_id: int, db: Session) -> dict:
    """Calcule les métriques agrégées depuis les 30 dernières sessions."""
    from sqlalchemy import text
    row = db.execute(text("""
        SELECT
            AVG("Session_AvgBpm")      AS avg_bpm,
            AVG("Session_Duration")    AS avg_duration,
            COUNT(*)                   AS session_count,
            AVG("User_Feedback_Score") AS avg_feedback
        FROM (
            SELECT "Session_AvgBpm","Session_Duration","User_Feedback_Score"
            FROM workout_sessions
            WHERE "User_ID" = :uid
            ORDER BY "Session_Date" DESC
            LIMIT 30
        ) sub
    """), {"uid": user_id}).mappings().first()
    if row is None or row["session_count"] == 0:
        return {"avg_bpm": 130.0, "avg_duration": 30.0, "session_count": 0, "avg_feedback": 3.0}
    return {
        "avg_bpm":       _safe_float(row["avg_bpm"], 130.0),
        "avg_duration":  _safe_float(row["avg_duration"], 30.0),
        "session_count": int(row["session_count"]),
        "avg_feedback":  _safe_float(row["avg_feedback"], 3.0),
    }


def _fetch_equipment(user_id: int, db: Session) -> list[str]:
    from sqlalchemy import text
    rows = db.execute(text("""
        SELECT e."Equipment_Name"
        FROM equipment e
        JOIN user_equipment ue ON ue."Equipment_ID" = e."Equipment_ID"
        WHERE ue."User_ID" = :uid
    """), {"uid": user_id}).fetchall()
    return [r[0] for r in rows if r[0]]


# ──────────────────────── Détermination niveau de forme ─────────────────────

def _compute_fitness_level(stats: dict, sessions_per_week: int) -> str:
    """Heuristique basée sur l'activité et le BPM au repos."""
    score = (stats["avg_duration"] * min(sessions_per_week, 7)) / max(stats["avg_bpm"], 1) * 10
    if score < 1.5:
        return "beginner"
    elif score < 3.5:
        return "intermediate"
    return "advanced"


# ──────────────────────── Catalogue d'exercices ────────────────────────────

_EXERCISE_CATALOG: dict[str, dict] = {
    "cardio": {
        "beginner":     ["Course légère 20 min", "Vélo stationnaire 25 min", "Marche rapide 30 min"],
        "intermediate": ["Course continue 30 min", "Vélo 35 min", "Corde à sauter 3×5 min"],
        "advanced":     ["Interval running 8×400m", "Vélo HIIT 40 min", "Rameur 30 min"],
    },
    "strength": {
        "beginner":     [
            ExerciseItem(name="Squat poids du corps", sets=3, reps="12-15", rest_seconds=60),
            ExerciseItem(name="Pompes genoux", sets=3, reps="10-12", rest_seconds=60),
            ExerciseItem(name="Fentes alternées", sets=3, reps="10/jambe", rest_seconds=60),
        ],
        "intermediate": [
            ExerciseItem(name="Squat barre", sets=4, reps="8-10", rest_seconds=90),
            ExerciseItem(name="Développé couché", sets=4, reps="8-10", rest_seconds=90),
            ExerciseItem(name="Soulevé de terre roumain", sets=3, reps="10-12", rest_seconds=90),
            ExerciseItem(name="Tirage horizontal", sets=3, reps="10-12", rest_seconds=90),
        ],
        "advanced":     [
            ExerciseItem(name="Squat barre lourde", sets=5, reps="5", rest_seconds=180),
            ExerciseItem(name="Développé couché lourd", sets=5, reps="5", rest_seconds=180),
            ExerciseItem(name="Soulevé de terre", sets=4, reps="4-6", rest_seconds=180),
            ExerciseItem(name="Tractions lestées", sets=4, reps="6-8", rest_seconds=120),
        ],
    },
    "hiit": {
        "beginner":     [
            ExerciseItem(name="Jumping jacks", sets=4, reps="20 sec actif / 40 sec repos", rest_seconds=40),
            ExerciseItem(name="Squats rapides", sets=4, reps="20 sec / 40 sec repos", rest_seconds=40),
        ],
        "intermediate": [
            ExerciseItem(name="Burpees", sets=5, reps="30 sec / 30 sec repos", rest_seconds=30),
            ExerciseItem(name="Mountain climbers", sets=5, reps="30 sec / 30 sec repos", rest_seconds=30),
            ExerciseItem(name="Box jumps", sets=4, reps="30 sec / 30 sec repos", rest_seconds=30),
        ],
        "advanced":     [
            ExerciseItem(name="Sprint 30/30", sets=8, reps="30 sec sprint / 30 sec marche", rest_seconds=30),
            ExerciseItem(name="Tabata squat-jump", sets=8, reps="20 sec / 10 sec repos", rest_seconds=10),
            ExerciseItem(name="Burpees enchaînés", sets=6, reps="40 sec / 20 sec repos", rest_seconds=20),
        ],
    },
    "yoga": {
        "beginner":     [
            ExerciseItem(name="Salutation au soleil A (×5)", sets=1, reps="5 cycles"),
            ExerciseItem(name="Posture de l'enfant – 2 min", sets=1, reps="2 min"),
            ExerciseItem(name="Posture du guerrier I – 30 sec/côté", sets=2, reps="30 sec"),
        ],
        "intermediate": [
            ExerciseItem(name="Salutation au soleil B (×8)"),
            ExerciseItem(name="Séquence guerrier I/II/III"),
            ExerciseItem(name="Posture de l'arbre – 1 min/côté"),
        ],
        "advanced":     [
            ExerciseItem(name="Ashtanga Primary Series – 45 min"),
            ExerciseItem(name="Inversions : poirier assisté"),
        ],
    },
    "flexibility": {
        "beginner":     [
            ExerciseItem(name="Étirement ischio-jambiers – 30 sec", sets=3, reps="30 sec"),
            ExerciseItem(name="Hip flexor stretch – 30 sec/côté", sets=3, reps="30 sec"),
        ],
        "intermediate": [
            ExerciseItem(name="Pigeon pose – 2 min/côté", sets=2, reps="2 min"),
            ExerciseItem(name="Fente profonde avec rotation"),
        ],
        "advanced":     [
            ExerciseItem(name="Grand écart progressif – 5 min"),
            ExerciseItem(name="Backbend wheel pose"),
        ],
    },
    "mixed": {
        "beginner":     [
            ExerciseItem(name="Circuit cardio/musculation 3 tours", sets=3, reps="10 répétitions"),
        ],
        "intermediate": [
            ExerciseItem(name="Circuit 4 tours – 5 exercices composés", sets=4, reps="12 reps"),
        ],
        "advanced":     [
            ExerciseItem(name="CrossFit WOD – 20 min AMRAP", sets=1, reps="max rounds"),
        ],
    },
}


def _build_exercises(workout_type: str, fitness: str) -> list[ExerciseItem]:
    catalog = _EXERCISE_CATALOG.get(workout_type, _EXERCISE_CATALOG["mixed"])
    raw = catalog.get(fitness, catalog.get("beginner", []))
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append(ExerciseItem(name=item))
        else:
            result.append(item)
    return result


def _warm_up() -> list[str]:
    return [
        "5 min marche / trot léger",
        "Rotations articulaires (chevilles, genoux, hanches, épaules)",
        "Étirements dynamiques : balancements de jambes 10×/côté",
    ]


def _cool_down() -> list[str]:
    return [
        "5 min marche lente",
        "Étirements statiques – quadriceps, ischio-jambiers, mollets (30 sec chacun)",
        "Respiration abdominale – 5 cycles",
    ]


# ──────────────────────── Contre-indications ───────────────────────────────

def _check_contraindications(injuries: Optional[str], workout_type: str) -> list[str]:
    if not injuries:
        return []
    warnings = []
    injuries_lower = injuries.lower()
    if any(k in injuries_lower for k in ["genou", "knee", "ménisque"]):
        if workout_type in ("hiit", "cardio"):
            warnings.append("Blessure au genou détectée – évitez les impacts élevés (sauts, course intense).")
    if any(k in injuries_lower for k in ["dos", "lombaire", "hernie"]):
        if workout_type == "strength":
            warnings.append("Problème lombaire détecté – évitez les charges lourdes en flexion.")
    if any(k in injuries_lower for k in ["épaule", "coiffe", "shoulder"]):
        if workout_type == "strength":
            warnings.append("Blessure à l'épaule – évitez les développés au-dessus de la tête.")
    return warnings


# ──────────────────────── Construction du plan hebdomadaire ────────────────

_REST_DAYS_MAP = {1: [2,3,4,5,6,7], 2: [2,4], 3: [3,6], 4: [3,6], 5: [3,7], 6: [4], 7: []}


def _build_weekly_plan(
    workout_type: str,
    intensity: str,
    duration_min: int,
    fitness: str,
    sessions_per_week: int,
) -> list[WorkoutSessionSchema]:
    rest_days = set(_REST_DAYS_MAP.get(sessions_per_week, []))
    sessions  = []
    day_count = 0
    for day in range(1, 8):
        if len(sessions) >= sessions_per_week:
            break
        if day in rest_days:
            continue
        exercises = _build_exercises(workout_type, fitness)
        sessions.append(WorkoutSessionSchema(
            day          = day,
            workout_type = workout_type,  # type: ignore[arg-type]
            intensity    = intensity,     # type: ignore[arg-type]
            duration_min = duration_min,
            exercises    = exercises,
            warm_up      = _warm_up(),
            cool_down    = _cool_down(),
        ))
    return sessions


# ──────────────────────── Point d'entrée ───────────────────────────────────

async def get_workout_recommendation(
    request: WorkoutRequest,
    db: Session,
    mongo: AsyncIOMotorDatabase,
    model: WorkoutModel,
) -> WorkoutResponse:
    # 1. Profil
    profile  = _fetch_user(request.user_id, db)
    stats    = _fetch_workout_stats(request.user_id, db)
    equipment= _fetch_equipment(request.user_id, db)

    age       = request.age       or profile.get("User_age") or 30
    gender_str= request.gender    or profile.get("User_gender") or "other"
    weight    = request.weight_kg or _safe_float(profile.get("User_weight"), 70.0)
    height    = request.height_cm or _safe_float(profile.get("User_Height"), 170.0)
    goal_str  = (request.goal     or profile.get("User_Goals") or "maintenance").lower().replace(" ", "_")
    goal_str  = goal_str if goal_str in GOAL_MAP else "maintenance"
    injuries  = request.injuries  or profile.get("User_Injuries")
    has_equip = int(bool(equipment or request.available_equipment))
    has_inj   = int(bool(injuries))
    bmi       = float(weight) / (float(height) / 100) ** 2

    # 2. Niveau de forme
    fitness_str = _compute_fitness_level(stats, request.sessions_per_week)

    # 3. Prédiction ML
    preds = model.predict(
        age              = int(age),
        gender           = GENDER_MAP.get(gender_str, 0.5),
        weight           = float(weight),
        height           = float(height),
        goal             = GOAL_MAP.get(goal_str, 2),
        fitness_level    = FITNESS_MAP.get(fitness_str, 0),
        avg_bpm          = stats["avg_bpm"],
        avg_duration     = stats["avg_duration"],
        sessions_per_week= request.sessions_per_week,
        has_equipment    = has_equip,
        has_injuries     = has_inj,
    )

    duration = request.preferred_duration_min or preds["duration_min"]

    # 4. Plan hebdomadaire
    weekly_plan = _build_weekly_plan(
        workout_type     = preds["workout_type"],
        intensity        = preds["intensity"],
        duration_min     = duration,
        fitness          = fitness_str,
        sessions_per_week= request.sessions_per_week,
    )

    # 5. Contre-indications
    contraindications = _check_contraindications(injuries, preds["workout_type"])

    # 6. Notes adaptatives
    adaptive_notes: list[str] = []
    if stats["session_count"] == 0:
        adaptive_notes.append("Premier programme généré – commencez doucement et écoutez votre corps.")
    if stats.get("avg_feedback", 3.0) < 2.5:
        adaptive_notes.append("Scores de feedback faibles détectés – intensité abaissée pour ce cycle.")

    # 7. LLM
    llm_advice = None
    if request.use_llm_enhancement:
        llm_advice = await enhance_workout_recommendation(
            age=int(age), gender=gender_str, bmi=bmi,
            goal=goal_str, fitness_level=fitness_str,
            workout_type=preds["workout_type"],
            intensity=preds["intensity"],
            duration_min=duration,
        )

    # 8. Persistance MongoDB
    rec_id = str(uuid.uuid4())
    now    = datetime.now(timezone.utc)
    await mongo["workout_recommendations"].insert_one({
        "_id":                 rec_id,
        "user_id":             request.user_id,
        "fitness_level":       fitness_str,
        "weekly_plan":         [s.model_dump() for s in weekly_plan],
        "contraindications":   contraindications,
        "model_version":       model.version,
        "generated_at":        now,
    })

    return WorkoutResponse(
        user_id               = request.user_id,
        recommendation_id     = rec_id,
        fitness_level_detected= fitness_str,  # type: ignore[arg-type]
        weekly_plan           = weekly_plan,
        adaptive_notes        = adaptive_notes,
        contraindications     = contraindications,
        llm_advice            = llm_advice,
        model_version         = model.version,
        generated_at          = now,
    )
