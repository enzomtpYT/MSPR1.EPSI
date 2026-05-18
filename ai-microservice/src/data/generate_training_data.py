"""
Génération de données d'entraînement synthétiques pour les modèles ML.

Les données sont basées sur des formules reconnues :
  - Calories : formule de Mifflin-St Jeor + facteur d'activité
  - Macros    : répartition selon l'objectif utilisateur
  - Fitness   : score calculé depuis les métriques d'entraînement

Usage :
    python -m src.data.generate_training_data
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

RANDOM_SEED = 42
N_SAMPLES = 5_000

rng = np.random.default_rng(RANDOM_SEED)

# ──────────────────────── Encodages catégoriels ────────────────────────────
GOAL_MAP = {
    "weight_loss": 0,
    "muscle_gain": 1,
    "maintenance": 2,
    "endurance": 3,
    "general_health": 4,
}
GENDER_MAP = {"female": 0, "male": 1, "other": 0.5}
ACTIVITY_MAP = {
    "sedentary": 1.2,
    "lightly_active": 1.375,
    "moderately_active": 1.55,
    "very_active": 1.725,
}
FITNESS_MAP = {"beginner": 0, "intermediate": 1, "advanced": 2}
WORKOUT_TYPE_MAP = {
    "cardio": 0, "strength": 1, "hiit": 2,
    "yoga": 3, "flexibility": 4, "mixed": 5,
}


def _mifflin_bmr(weight: float, height: float, age: int, gender: str) -> float:
    """Métabolisme de base (Mifflin-St Jeor)."""
    base = 10 * weight + 6.25 * height - 5 * age
    return base + 5 if gender == "male" else base - 161


def _macro_split(goal: str, calories: float) -> tuple[float, float, float, float]:
    """Répartition protéines / glucides / lipides / fibres selon l'objectif."""
    splits = {
        "weight_loss":    (0.35, 0.35, 0.30),
        "muscle_gain":    (0.30, 0.45, 0.25),
        "maintenance":    (0.25, 0.50, 0.25),
        "endurance":      (0.20, 0.55, 0.25),
        "general_health": (0.25, 0.50, 0.25),
    }
    # Fibre recommandée : ~14 g par 1000 kcal (DRI), modulée par objectif + bruit
    fiber_base = {
        "weight_loss":    14.0 / 1000,
        "muscle_gain":    12.0 / 1000,
        "maintenance":    14.0 / 1000,
        "endurance":      16.0 / 1000,
        "general_health": 15.0 / 1000,
    }
    p_ratio, c_ratio, f_ratio = splits.get(goal, splits["maintenance"])
    protein_g = calories * p_ratio / 4
    carbs_g   = calories * c_ratio / 4
    fat_g     = calories * f_ratio / 9
    fiber_base_g = calories * fiber_base.get(goal, 14.0 / 1000)
    fiber_g   = fiber_base_g + rng.uniform(-3, 3)
    return round(protein_g, 1), round(carbs_g, 1), round(fat_g, 1), round(fiber_g, 1)


def _fitness_level(avg_bpm: float, avg_duration: float, sessions_wk: float) -> str:
    score = (avg_duration * sessions_wk) / max(avg_bpm, 1) * 10
    if score < 1.5:
        return "beginner"
    elif score < 3.5:
        return "intermediate"
    return "advanced"


def _recommend_workout(goal: str, fitness: str, has_equipment: bool) -> str:
    matrix = {
        ("weight_loss",    "beginner"):     "cardio",
        ("weight_loss",    "intermediate"): "hiit",
        ("weight_loss",    "advanced"):     "hiit",
        ("muscle_gain",    "beginner"):     "strength",
        ("muscle_gain",    "intermediate"): "strength",
        ("muscle_gain",    "advanced"):     "strength",
        ("endurance",      "beginner"):     "cardio",
        ("endurance",      "intermediate"): "cardio",
        ("endurance",      "advanced"):     "mixed",
        ("maintenance",    "beginner"):     "mixed",
        ("maintenance",    "intermediate"): "mixed",
        ("maintenance",    "advanced"):     "mixed",
        ("general_health", "beginner"):     "yoga",
        ("general_health", "intermediate"): "flexibility",
        ("general_health", "advanced"):     "mixed",
    }
    base = matrix.get((goal, fitness), "mixed")
    if not has_equipment and base == "strength":
        base = "hiit"
    return base


def generate_nutrition_dataset() -> pd.DataFrame:
    """Génère N_SAMPLES lignes pour entraîner le modèle nutritionnel."""
    goals    = rng.choice(list(GOAL_MAP.keys()),    size=N_SAMPLES)
    genders  = rng.choice(list(GENDER_MAP.keys()),  size=N_SAMPLES)
    activity = rng.choice(list(ACTIVITY_MAP.keys()), size=N_SAMPLES)

    ages    = rng.integers(18, 70,  size=N_SAMPLES)
    weights = rng.uniform(45, 130,  size=N_SAMPLES)
    heights = rng.uniform(150, 200, size=N_SAMPLES)

    rows = []
    for i in range(N_SAMPLES):
        bmr  = _mifflin_bmr(weights[i], heights[i], ages[i], genders[i])
        tdee = bmr * ACTIVITY_MAP[activity[i]]
        # Ajustement selon l'objectif
        if goals[i] == "weight_loss":
            calories = tdee * rng.uniform(0.75, 0.90)
        elif goals[i] == "muscle_gain":
            calories = tdee * rng.uniform(1.05, 1.15)
        else:
            calories = tdee * rng.uniform(0.95, 1.05)

        calories = round(calories, 1)
        bmi      = round(weights[i] / (heights[i] / 100) ** 2, 2)
        protein, carbs, fat, fiber = _macro_split(goals[i], calories)

        rows.append({
            "age":            int(ages[i]),
            "gender":         GENDER_MAP[genders[i]],
            "weight":         round(weights[i], 2),
            "height":         round(heights[i], 2),
            "bmi":            bmi,
            "goal":           GOAL_MAP[goals[i]],
            "activity_level": ACTIVITY_MAP[activity[i]],
            "target_calories": calories,
            "target_protein":  protein,
            "target_carbs":    carbs,
            "target_fat":      fat,
            "target_fiber":    fiber,
        })
    return pd.DataFrame(rows)


def generate_workout_dataset() -> pd.DataFrame:
    """Génère N_SAMPLES lignes pour entraîner le modèle d'entraînement."""
    goals   = rng.choice(list(GOAL_MAP.keys()),    size=N_SAMPLES)
    fitness = rng.choice(list(FITNESS_MAP.keys()), size=N_SAMPLES)

    avg_bpm      = rng.uniform(60, 180, size=N_SAMPLES)
    avg_duration = rng.uniform(15, 90,  size=N_SAMPLES)
    sessions_wk  = rng.integers(1, 7,   size=N_SAMPLES).astype(float)
    has_equipment = rng.integers(0, 2,  size=N_SAMPLES)  # 0/1
    has_injuries  = rng.integers(0, 2,  size=N_SAMPLES)  # 0/1
    ages    = rng.integers(18, 70,  size=N_SAMPLES)
    weights = rng.uniform(45, 130,  size=N_SAMPLES)
    heights = rng.uniform(150, 200, size=N_SAMPLES)

    rows = []
    for i in range(N_SAMPLES):
        wtype    = _recommend_workout(goals[i], fitness[i], bool(has_equipment[i]))
        bmi      = round(weights[i] / (heights[i] / 100) ** 2, 2)

        # Durée recommandée selon intensité et objectif
        if goals[i] in ("weight_loss", "endurance"):
            duration = int(rng.integers(40, 75))
        elif goals[i] == "muscle_gain":
            duration = int(rng.integers(45, 70))
        else:
            duration = int(rng.integers(30, 60))

        # Intensité selon fitness
        intensity_map = {"beginner": 0, "intermediate": 1, "advanced": 2}

        rows.append({
            "age":            int(ages[i]),
            "gender":         rng.choice([0.0, 1.0]),
            "weight":         round(weights[i], 2),
            "height":         round(heights[i], 2),
            "bmi":            bmi,
            "goal":           GOAL_MAP[goals[i]],
            "fitness_level":  FITNESS_MAP[fitness[i]],
            "avg_bpm":        round(avg_bpm[i], 1),
            "avg_duration":   round(avg_duration[i], 1),
            "sessions_per_week": int(sessions_wk[i]),
            "has_equipment":  int(has_equipment[i]),
            "has_injuries":   int(has_injuries[i]),
            # Cibles
            "workout_type":   WORKOUT_TYPE_MAP[wtype],
            "intensity":      intensity_map[fitness[i]],
            "duration_min":   duration,
        })
    return pd.DataFrame(rows)


def save_datasets(output_dir: Path = Path("data")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Génération du dataset nutritionnel …")
    df_nut = generate_nutrition_dataset()
    out_nut = output_dir / "nutrition_training.csv"
    df_nut.to_csv(out_nut, index=False)
    print(f"  → {len(df_nut)} lignes enregistrées dans {out_nut}")

    print("Génération du dataset d'entraînement sportif …")
    df_wkt = generate_workout_dataset()
    out_wkt = output_dir / "workout_training.csv"
    df_wkt.to_csv(out_wkt, index=False)
    print(f"  → {len(df_wkt)} lignes enregistrées dans {out_wkt}")


if __name__ == "__main__":
    save_datasets()
