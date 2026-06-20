"""
HealthAI Coach – AI Microservice
Point d'entrée FastAPI.

Démarrage :
    uvicorn src.app:app --reload --port 8001
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.config import settings
from src.database import close_mongo_connection
from src.models.nutrition_model import NutritionModel
from src.models.workout_model import WorkoutModel
from src.router import health, nutrition, workout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────── Cycle de vie ─────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Démarrage du microservice IA …")

    # Chargement / entraînement des modèles ML
    app.state.nutrition_model = NutritionModel()
    app.state.nutrition_model.load_or_train()
    logger.info("Modèle nutritionnel prêt (v%s)", app.state.nutrition_model.version)

    app.state.workout_model = WorkoutModel()
    app.state.workout_model.load_or_train()
    logger.info("Modèle sportif prêt (v%s)", app.state.workout_model.version)

    yield  # ← l'application est active ici

    logger.info("Arrêt du microservice – fermeture des connexions …")
    await close_mongo_connection()


# ──────────────────────── Application ──────────────────────────────────────

app = FastAPI(
    title="HealthAI Coach – AI Microservice",
    description=(
        "Moteur de recommandations personnalisées en nutrition et en activité "
        "physique, basé sur des modèles ML (Random Forest, Gradient Boosting) "
        "et enrichi optionnellement par un LLM (Ollama / Hugging Face)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router,    prefix="/api/v1",           tags=["Health"])
app.include_router(nutrition.router, prefix="/api/v1/nutrition", tags=["Nutrition"])
app.include_router(workout.router,   prefix="/api/v1/workout",   tags=["Workout"])

Instrumentator().instrument(app).expose(app)
