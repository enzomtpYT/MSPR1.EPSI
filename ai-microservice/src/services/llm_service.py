"""
Service LLM : enrichissement des recommandations via Ollama (local) ou
Hugging Face Inference API (cloud).

Le service est conçu avec un mécanisme de fallback : si le LLM est
indisponible, le service renvoie None sans lever d'exception, permettant
à l'application de continuer avec les recommandations ML seules.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from mistralai.client import Mistral

from src.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


# ──────────────────────── Prompt templates ─────────────────────────────────

_NUTRITION_PROMPT = """Tu es un expert en nutrition sportive.
Voici le profil d'un utilisateur :
- Âge : {age} ans | Genre : {gender} | Poids : {weight} kg | Taille : {height} cm
- Objectif : {goal}
- Niveau d'activité : {activity_level}
- Calories recommandées : {calories} kcal/jour
- Macros : Protéines {protein_g}g | Glucides {carbs_g}g | Lipides {fat_g}g

Donne 3 à 5 conseils pratiques, concis et personnalisés pour aider cet utilisateur
à atteindre son objectif nutritionnel. Réponds en français, en liste à puces."""

_WORKOUT_PROMPT = """Tu es un coach sportif professionnel.
Voici le profil d'un utilisateur :
- Âge : {age} ans | Genre : {gender} | IMC : {bmi:.1f}
- Objectif : {goal}
- Niveau de forme : {fitness_level}
- Programme recommandé : {workout_type} ({intensity}), {duration_min} min/séance

Donne 3 à 5 conseils pratiques et motivants pour optimiser ce programme.
Mentionne des points de vigilance si nécessaire. Réponds en français, en liste à puces."""


# ──────────────────────── Fournisseurs ─────────────────────────────────────

async def _call_ollama(prompt: str) -> Optional[str]:
    url = f"{settings.OLLAMA_URL}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 300},
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip() or None
    except Exception as exc:
        logger.warning("Ollama indisponible : %s", exc)
        return None


async def _call_mistral(prompt: str) -> Optional[str]:
    """Appelle l'API Mistral Cloud pour la génération de texte."""
    if not settings.MISTRAL_API_KEY:
        logger.warning("MISTRAL_API_KEY non configurée – LLM désactivé.")
        return None

    try:
        async with Mistral(api_key=settings.MISTRAL_API_KEY) as client:
            response = await client.chat.complete_async(
                model=settings.MISTRAL_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.7,
            )
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if isinstance(content, str):
                    text = content.strip()
                    return text or None
    except Exception as exc:
        logger.warning("Mistral API indisponible : %s", exc)
        return None


async def _call_llm(prompt: str) -> Optional[str]:
    """Appelle le fournisseur LLM configuré."""
    if settings.LLM_PROVIDER == "mistral":
        return await _call_mistral(prompt)
    return await _call_ollama(prompt)


# ──────────────────────── API publique ─────────────────────────────────────

async def enhance_nutrition_recommendation(
    age: int,
    gender: str,
    weight: float,
    height: float,
    goal: str,
    activity_level: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
) -> Optional[str]:
    """Génère des conseils nutritionnels via LLM (None si LLM indisponible)."""
    prompt = _NUTRITION_PROMPT.format(
        age=age, gender=gender, weight=weight, height=height,
        goal=goal, activity_level=activity_level,
        calories=calories, protein_g=protein_g,
        carbs_g=carbs_g, fat_g=fat_g,
    )
    return await _call_llm(prompt)


async def enhance_workout_recommendation(
    age: int,
    gender: str,
    bmi: float,
    goal: str,
    fitness_level: str,
    workout_type: str,
    intensity: str,
    duration_min: int,
) -> Optional[str]:
    """Génère des conseils sportifs via LLM (None si LLM indisponible)."""
    prompt = _WORKOUT_PROMPT.format(
        age=age, gender=gender, bmi=bmi,
        goal=goal, fitness_level=fitness_level,
        workout_type=workout_type, intensity=intensity,
        duration_min=duration_min,
    )
    return await _call_llm(prompt)


# ──────────────────────── Mistral Vision API ──────────────────────────────

import json
from typing import Any

_MEAL_ANALYSIS_PROMPT = """Analyse cette image de repas. Liste les aliments présents et estime les calories totales ainsi que la répartition des macronutriments (Protéines, Glucides, Lipides). Réponds au format JSON avec les clés exactes: foods (liste de strings), estimated_calories (nombre), estimated_protein (nombre en g), estimated_carbs (nombre en g), estimated_fat (nombre en g). Réponse JSON uniquement, pas d'autre texte."""


async def analyze_meal_image(image_base64: str) -> Optional[dict[str, Any]]:
    """
    Analyse une image de repas via l'API Mistral Vision (Pixtral).
    
    Args:
        image_base64: La donnée base64 de l'image (sans préfixe data:image/...)
    
    Returns:
        Dict contenant: foods, estimated_calories, estimated_protein, estimated_carbs, estimated_fat
        None si la requête échoue.
    """
    if not settings.MISTRAL_API_KEY:
        logger.warning("MISTRAL_API_KEY non configurée – vision désactivée.")
        return None

    try:
        async with Mistral(api_key=settings.MISTRAL_API_KEY) as client:
            response = await client.chat.complete_async(
                model=settings.MISTRAL_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": _MEAL_ANALYSIS_PROMPT,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500,
            )

            # Extraire le contenu de la réponse
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if isinstance(content, str):
                    # Parser JSON
                    parsed = json.loads(content.strip())
                    return parsed
    except json.JSONDecodeError as exc:
        logger.warning("Mistral Vision : erreur de parsing JSON : %s", exc)
        return None
    except Exception as exc:
        logger.warning("Mistral Vision API indisponible : %s", exc)
        return None
