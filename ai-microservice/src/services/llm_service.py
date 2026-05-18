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


async def _call_huggingface(prompt: str) -> Optional[str]:
    if not settings.HF_API_KEY:
        logger.warning("HF_API_KEY non configurée – LLM désactivé.")
        return None

    url = f"https://api-inference.huggingface.co/models/{settings.HF_MODEL}"
    headers = {"Authorization": f"Bearer {settings.HF_API_KEY}"}
    # Format Instruction pour Mistral
    formatted = f"<s>[INST] {prompt} [/INST]"
    payload = {"inputs": formatted, "parameters": {"max_new_tokens": 300, "temperature": 0.7}}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                text = data[0].get("generated_text", "")
                # Retirer le prompt de la réponse
                if "[/INST]" in text:
                    text = text.split("[/INST]", 1)[-1]
                return text.strip() or None
    except Exception as exc:
        logger.warning("Hugging Face API indisponible : %s", exc)
        return None


async def _call_llm(prompt: str) -> Optional[str]:
    """Appelle le fournisseur LLM configuré."""
    if settings.LLM_PROVIDER == "huggingface":
        return await _call_huggingface(prompt)
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
