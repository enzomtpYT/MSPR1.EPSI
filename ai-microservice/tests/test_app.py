"""Tests d'intégration HTTP via TestClient FastAPI."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_model_metrics_endpoint(client: TestClient):
    response = client.get("/api/v1/models/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "nutrition_model" in data
    assert "workout_model" in data


def test_openapi_schema_available(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    # Vérifie que les routes clés sont documentées
    assert "/api/v1/nutrition/recommend" in schema["paths"]
    assert "/api/v1/workout/recommend" in schema["paths"]
