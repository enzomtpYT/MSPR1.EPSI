# HealthAI Coach – AI Microservice

Micro-service FastAPI indépendant qui expose un **moteur de recommandations IA** en nutrition et en activité physique pour la plateforme HealthAI Coach.

## Architecture

```
ai-microservice/
├── src/
│   ├── app.py                        # Entrypoint FastAPI (port 8001)
│   ├── config.py                     # Settings (env vars)
│   ├── database.py                   # Connexions PostgreSQL (lecture) + MongoDB
│   ├── data/
│   │   └── generate_training_data.py # Génération données synthétiques
│   ├── models/
│   │   ├── nutrition_model.py        # Random Forest multi-sorties
│   │   └── workout_model.py          # Gradient Boosting + Decision Tree
│   ├── schemas/
│   │   ├── nutrition.py              # Pydantic I/O nutrition
│   │   └── workout.py                # Pydantic I/O workout
│   ├── services/
│   │   ├── nutrition_service.py      # Orchestration recommandation nutrition
│   │   ├── workout_service.py        # Orchestration recommandation workout
│   │   └── llm_service.py            # Ollama / Hugging Face
│   └── router/
│       ├── nutrition.py
│       ├── workout.py
│       └── health.py
├── tests/
│   ├── conftest.py
│   ├── test_nutrition.py
│   ├── test_workout.py
│   └── test_app.py
├── artifacts/                        # Modèles joblib (auto-générés)
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

## Démarrage rapide

### 1. Prérequis

- Python 3.11+
- PostgreSQL (base MSPR1 existante)
- MongoDB 7 (ou via Docker)

### 2. Installation

```bash
cd ai-microservice
cp .env.example .env   # puis renseigner les variables
pip install ".[dev]"
```

### 3. Lancement local

```bash
uvicorn src.app:app --reload --port 8001
```

Au démarrage, les modèles ML sont automatiquement entraînés sur 5 000 profils synthétiques (≈ 30 s) et sauvegardés dans `artifacts/`.

### 4. Lancement via Docker

```bash
docker compose up --build
```

### 5. Documentation API

- Swagger UI : http://localhost:8001/docs
- ReDoc      : http://localhost:8001/redoc
- OpenAPI JSON : http://localhost:8001/openapi.json

## Endpoints principaux

| Méthode | Route | Description |
|---------|-------|-------------|
| `POST` | `/api/v1/nutrition/recommend` | Recommandation nutritionnelle |
| `GET`  | `/api/v1/nutrition/history/{user_id}` | Historique nutrition (MongoDB) |
| `POST` | `/api/v1/workout/recommend` | Programme d'entraînement |
| `GET`  | `/api/v1/workout/history/{user_id}` | Historique workout (MongoDB) |
| `GET`  | `/api/v1/health` | Santé du service |
| `GET`  | `/api/v1/models/metrics` | Métriques ML (MAE, R², F1) |
| `POST` | `/api/v1/models/retrain` | Ré-entraîner les modèles |

## Modèles ML

### Nutrition – `MultiOutputRegressor(RandomForestRegressor)`

| Cible | Algorithme | Métrique |
|-------|-----------|---------|
| Calories journalières | Random Forest | R² > 0.95, MAE < 80 kcal |
| Protéines (g) | Random Forest | R² > 0.95 |
| Glucides (g) | Random Forest | R² > 0.95 |
| Lipides (g) | Random Forest | R² > 0.95 |
| Fibres (g) | Random Forest | R² > 0.90 |

**Features** : âge, genre, poids, taille, IMC, objectif, facteur d'activité  
**Données** : 5 000 profils synthétiques (formule Mifflin-St Jeor + bruit réaliste)  
**Split** : 80 % train / 20 % test  
**Optimisation** : GridSearchCV (n_estimators, max_depth)

### Workout – Gradient Boosting + Decision Tree

| Cible | Algorithme | Métrique |
|-------|-----------|---------|
| Type d'entraînement (6 classes) | GradientBoostingClassifier | Accuracy > 0.85, F1 > 0.80 |
| Intensité (3 niveaux) | DecisionTreeClassifier | Accuracy > 0.85 |
| Durée (minutes) | GradientBoostingRegressor | MAE < 8 min, R² > 0.85 |

**Features** : âge, genre, IMC, objectif, niveau fitness, BPM moyen, durée moyenne séances, séances/semaine, équipement, blessures

## Intégration avec le backend MSPR1

Le microservice se connecte en **lecture seule** à la base PostgreSQL existante pour charger :
- `users` → profil complet de l'utilisateur
- `workout_sessions` → historique pour calculer le niveau de forme
- `products` → catalogue alimentaire pour construire le plan de repas
- `equipment` → matériel disponible pour l'utilisateur

Les recommandations générées sont stockées dans **MongoDB** (collections `nutrition_recommendations` et `workout_recommendations`).

## LLM – Enrichissement optionnel

Activez `use_llm_enhancement: true` dans la requête pour obtenir des conseils personnalisés rédigés par un LLM :

- **Ollama** (défaut) : modèle local Mistral – `LLM_PROVIDER=ollama`
- **Hugging Face** : `LLM_PROVIDER=huggingface` + `HF_API_KEY`

En cas d'indisponibilité du LLM, le service répond normalement avec les recommandations ML (fallback gracieux).

## Tests

```bash
# Tous les tests avec couverture
pytest

# Rapport HTML de couverture
open coverage_report/index.html
```

Couverture cible : **≥ 70 %**
