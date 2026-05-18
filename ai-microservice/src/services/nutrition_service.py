"""
Service métier – Recommandations nutritionnelles.

Orchestration :
 1. Lecture du profil utilisateur dans PostgreSQL
 2. Prédiction des cibles macros via le modèle ML
 3. Sélection de produits depuis la DB (filtres : allergies, budget, régime)
 4. Construction du plan de repas
 5. Détection des déséquilibres
 6. Enrichissement optionnel via LLM
 7. Persistance de la recommandation dans MongoDB
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.orm import Session

from src.models.nutrition_model import NutritionModel
from src.schemas.nutrition import (
    MacroTargets,
    MealPlanItem,
    NutritionRequest,
    NutritionResponse,
)
from src.services.llm_service import enhance_nutrition_recommendation, analyze_meal_image

logger = logging.getLogger(__name__)

# ── Encodages (miroir de generate_training_data.py) ────────────────────────
GOAL_MAP = {
    "weight_loss": 0, "muscle_gain": 1, "maintenance": 2,
    "endurance": 3, "general_health": 4,
}
ACTIVITY_MAP = {
    "sedentary": 1.2, "lightly_active": 1.375,
    "moderately_active": 1.55, "very_active": 1.725,
}
GENDER_MAP = {"female": 0.0, "male": 1.0, "other": 0.5}


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


# ──────────────────────── Lecture DB PostgreSQL ────────────────────────────

def _fetch_user_profile(user_id: int, db: Session) -> dict:
    """Charge le profil depuis la table `users` du backend MSPR1."""
    from sqlalchemy import text
    row = db.execute(
        text("SELECT * FROM users WHERE \"User_ID\" = :uid"), {"uid": user_id}
    ).mappings().first()
    if row is None:
        raise ValueError(f"Utilisateur {user_id} introuvable dans la base.")
    return dict(row)


def _fetch_products(db: Session, allergies: Optional[str], budget: Optional[str],
                    dietary_prefs: Optional[str], limit: int = 50) -> list[dict]:
    """Charge les produits compatibles avec les contraintes de l'utilisateur."""
    from sqlalchemy import text
    query = 'SELECT * FROM products WHERE 1=1'
    params: dict = {}

    if budget and budget in ("low", "medium"):
        query += ' AND "Product_Price_Category" = :budget'
        params["budget"] = budget

    # Filtre régime via tags (ex: "vegan", "gluten_free")
    if dietary_prefs:
        # Recherche partielle sur Product_Diet_Tags
        query += ' AND "Product_Diet_Tags" ILIKE :pref'
        params["pref"] = f"%{dietary_prefs.split(',')[0].strip()}%"

    query += f' LIMIT {limit}'
    rows = db.execute(text(query), params).mappings().all()
    return [dict(r) for r in rows]


# ──────────────────────── Construction du plan ─────────────────────────────

_MEAL_SLOTS = ["petit-déjeuner", "déjeuner", "dîner", "collation matin", "collation après-midi", "souper"]


def _build_meal_plan(
    products: list[dict],
    macro_targets: MacroTargets,
    nb_meals: int,
) -> list[MealPlanItem]:
    """Répartit les macros sur les repas et associe un produit à chaque slot."""
    items: list[MealPlanItem] = []
    cal_per_meal = macro_targets.calories / nb_meals

    for i in range(min(nb_meals, len(_MEAL_SLOTS))):
        slot = _MEAL_SLOTS[i]
        # Choisir le produit le plus proche en termes de kcal / 100g
        product = _pick_product(products, cal_per_meal, used_ids={it.product_id for it in items})

        if product is None:
            continue

        kcal_per_100g = _safe_float(product.get("product_kcal"), 100.0) or 100.0
        portion_g     = max(50.0, round((cal_per_meal / kcal_per_100g) * 100, 0))
        ratio         = portion_g / 100.0

        items.append(MealPlanItem(
            meal_slot   = slot,
            product_id  = product.get("Product_ID"),
            product_name= product.get("product_name", "Aliment inconnu"),
            portion_g   = portion_g,
            kcal        = round(kcal_per_100g * ratio, 1),
            protein_g   = round(_safe_float(product.get("product_protein")) * ratio, 1),
            carbs_g     = round(_safe_float(product.get("product_carbs")) * ratio, 1),
            fat_g       = round(_safe_float(product.get("product_fat")) * ratio, 1),
        ))
    return items


def _pick_product(
    products: list[dict], target_kcal: float, used_ids: set
) -> Optional[dict]:
    """Retourne le produit dont la valeur calorique / 100g est la plus proche de target_kcal."""
    candidates = [p for p in products if p.get("Product_ID") not in used_ids]
    if not candidates:
        candidates = products  # réutilisation si liste épuisée
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda p: abs(_safe_float(p.get("product_kcal"), 100) - target_kcal),
    )


# ──────────────────────── Détection des déséquilibres ──────────────────────

def _detect_imbalances(
    meal_plan: list[MealPlanItem], targets: MacroTargets
) -> tuple[list[str], list[str]]:
    actual_cal  = sum(i.kcal for i in meal_plan)
    actual_prot = sum(i.protein_g for i in meal_plan)
    actual_carbs= sum(i.carbs_g for i in meal_plan)
    actual_fat  = sum(i.fat_g for i in meal_plan)

    deficits, excesses = [], []

    if actual_cal < targets.calories * 0.85:
        deficits.append(f"Apport calorique insuffisant ({actual_cal:.0f} kcal vs {targets.calories:.0f} kcal cibles)")
    if actual_cal > targets.calories * 1.15:
        excesses.append(f"Apport calorique excessif ({actual_cal:.0f} kcal vs {targets.calories:.0f} kcal cibles)")
    if actual_prot < targets.protein_g * 0.80:
        deficits.append(f"Déficit protéique ({actual_prot:.0f}g vs {targets.protein_g:.0f}g recommandés)")
    if actual_carbs > targets.carbs_g * 1.20:
        excesses.append(f"Excès de glucides ({actual_carbs:.0f}g vs {targets.carbs_g:.0f}g recommandés)")
    if actual_fat > targets.fat_g * 1.20:
        excesses.append(f"Excès de lipides ({actual_fat:.0f}g vs {targets.fat_g:.0f}g recommandés)")

    return deficits, excesses


# ──────────────────────── Point d'entrée ───────────────────────────────────

async def get_nutrition_recommendation(
    request: NutritionRequest,
    db: Session,
    mongo: AsyncIOMotorDatabase,
    model: NutritionModel,
) -> NutritionResponse:
    # 1. Profil utilisateur (DB ou payload)
    profile = _fetch_user_profile(request.user_id, db)

    age       = request.age       or profile.get("User_age") or 30
    gender_str= request.gender    or profile.get("User_gender") or "other"
    weight    = request.weight_kg or _safe_float(profile.get("User_weight"), 70.0)
    height    = request.height_cm or _safe_float(profile.get("User_Height"), 170.0)
    goal_str  = request.goal      or profile.get("User_Goals") or "maintenance"
    activity  = request.activity_level or "moderately_active"
    allergies = request.allergies or profile.get("User_Allergies")
    diet_pref = request.dietary_preferences or profile.get("User_Dietary_Preferences")
    budget    = request.budget_level or profile.get("User_Budget_Level")

    # Normalisation
    goal_str  = goal_str.lower().replace(" ", "_") if goal_str else "maintenance"
    goal_str  = goal_str if goal_str in GOAL_MAP else "maintenance"

    # 2. Prédiction ML
    preds = model.predict(
        age           = int(age),
        gender        = GENDER_MAP.get(gender_str, 0.5),
        weight        = float(weight),
        height        = float(height),
        goal          = GOAL_MAP.get(goal_str, 2),
        activity_level= ACTIVITY_MAP.get(activity, 1.55),
    )

    macro_targets = MacroTargets(
        calories  = preds["calories"],
        protein_g = preds["protein_g"],
        carbs_g   = preds["carbs_g"],
        fat_g     = preds["fat_g"],
        fiber_g   = preds["fiber_g"],
    )

    # 3. Produits compatibles
    products = _fetch_products(db, allergies, budget, diet_pref)

    # 4. Plan de repas
    meal_plan = _build_meal_plan(products, macro_targets, request.nb_meals_per_day)

    # 5. Déséquilibres
    deficits, excesses = _detect_imbalances(meal_plan, macro_targets)

    # 6. Vision – Analyse de l'image du repas (optionnel)
    detected_foods: Optional[list[str]] = None
    detected_macros: Optional[dict] = None
    if request.meal_image_base64:
        vision_result = await analyze_meal_image(request.meal_image_base64)
        if vision_result:
            detected_foods = vision_result.get("foods", [])
            detected_macros = {
                "estimated_calories": vision_result.get("estimated_calories"),
                "estimated_protein": vision_result.get("estimated_protein"),
                "estimated_carbs": vision_result.get("estimated_carbs"),
                "estimated_fat": vision_result.get("estimated_fat"),
            }
            logger.info(f"Aliments détectés : {detected_foods}")

    # 7. LLM (optionnel)
    llm_advice = None
    if request.use_llm_enhancement:
        llm_advice = await enhance_nutrition_recommendation(
            age=int(age), gender=gender_str, weight=float(weight), height=float(height),
            goal=goal_str, activity_level=activity,
            calories=preds["calories"], protein_g=preds["protein_g"],
            carbs_g=preds["carbs_g"], fat_g=preds["fat_g"],
        )

    # 8. Persistance MongoDB
    rec_id = str(uuid.uuid4())
    now    = datetime.now(timezone.utc)
    await mongo["nutrition_recommendations"].insert_one({
        "_id":            rec_id,
        "user_id":        request.user_id,
        "macro_targets":  macro_targets.model_dump(),
        "meal_plan":      [i.model_dump() for i in meal_plan],
        "deficit_warnings": deficits,
        "excess_warnings":  excesses,
        "detected_foods":   detected_foods,
        "detected_macros":  detected_macros,
        "model_version":  model.version,
        "generated_at":   now,
    })

    return NutritionResponse(
        user_id          = request.user_id,
        recommendation_id= rec_id,
        macro_targets    = macro_targets,
        meal_plan        = meal_plan,
        deficit_warnings = deficits,
        excess_warnings  = excesses,
        llm_advice       = llm_advice,
        detected_foods   = detected_foods,
        detected_macros  = detected_macros,
        model_version    = model.version,
        generated_at     = now,
    )
