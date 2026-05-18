"""
Fixtures pytest partagées pour l'ensemble des tests du microservice IA.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.nutrition_model import NutritionModel
from src.models.workout_model import WorkoutModel


# ─────────────────────── Modèles ML (entraîné sur données synthétiques) ────

@pytest.fixture(scope="session")
def nutrition_model() -> NutritionModel:
    model = NutritionModel()
    model.train()
    return model


@pytest.fixture(scope="session")
def workout_model() -> WorkoutModel:
    model = WorkoutModel()
    model.train()
    return model


# ─────────────────────── DB PostgreSQL (mock) ───────────────────────────────

@pytest.fixture
def mock_pg_db():
    """Simule une session SQLAlchemy retournant un utilisateur et des produits fictifs."""
    db = MagicMock()

    fake_user = {
        "User_ID": 1,
        "User_mail": "test@example.com",
        "User_age": 30,
        "User_gender": "male",
        "User_weight": 80.0,
        "User_Height": 178.0,
        "User_Goals": "weight_loss",
        "User_Allergies": None,
        "User_Dietary_Preferences": None,
        "User_Budget_Level": "medium",
        "User_Injuries": None,
        "User_Subscription": "premium",
    }

    fake_products = [
        {
            "Product_ID": i,
            "product_name": f"Produit test {i}",
            "product_kcal": 150.0 + i * 20,
            "product_protein": 10.0 + i,
            "product_carbs": 20.0 + i,
            "product_fat": 5.0,
            "product_fiber": 3.0,
            "Product_Diet_Tags": "balanced",
            "Product_Price_Category": "medium",
        }
        for i in range(1, 10)
    ]

    fake_workout_stats = MagicMock()
    fake_workout_stats.__iter__ = MagicMock(return_value=iter([]))
    fake_workout_stats.mappings = MagicMock(return_value=MagicMock(
        first=MagicMock(return_value={
            "avg_bpm": 140.0, "avg_duration": 40.0,
            "session_count": 10, "avg_feedback": 3.5,
        })
    ))

    def execute_side_effect(query, params=None):
        q = str(query).lower()
        result = MagicMock()
        if "users" in q and "user_id" in q:
            mapping = MagicMock()
            mapping.first = MagicMock(return_value=fake_user)
            result.mappings = MagicMock(return_value=mapping)
        elif "products" in q:
            result.mappings = MagicMock(return_value=MagicMock(all=MagicMock(return_value=fake_products)))
        elif "workout_sessions" in q:
            mapping = MagicMock()
            mapping.first = MagicMock(return_value={
                "avg_bpm": 140.0, "avg_duration": 40.0,
                "session_count": 10, "avg_feedback": 3.5,
            })
            result.mappings = MagicMock(return_value=mapping)
        elif "equipment" in q:
            result.fetchall = MagicMock(return_value=[])
        else:
            result.mappings = MagicMock(return_value=MagicMock(first=MagicMock(return_value={})))
        return result

    db.execute = MagicMock(side_effect=execute_side_effect)
    return db


# ─────────────────────── MongoDB (mock) ─────────────────────────────────────

@pytest.fixture
def mock_mongo():
    """Simule une base MongoDB asynchrone."""
    mongo = MagicMock()
    collection = MagicMock()
    collection.insert_one  = AsyncMock(return_value=None)
    collection.find        = MagicMock(return_value=_async_cursor([]))
    mongo.__getitem__      = MagicMock(return_value=collection)
    return mongo


class _async_cursor:
    """Curseur asynchrone factice pour les tests."""
    def __init__(self, items):
        self._items = iter(items)

    def sort(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration
