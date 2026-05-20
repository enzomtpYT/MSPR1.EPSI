import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    def __init__(self) -> None:
        # PostgreSQL (lecture seule — base existante du backend)
        self.POSTGRES_URL: str = os.getenv(
            "POSTGRES_URL",
            "postgresql://postgres:postgres@localhost:5432/mspr_db",
        )
        # MongoDB (stockage des recommandations — NoSQL)
        self.MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        self.MONGO_DB: str = os.getenv("MONGO_DB", "healthai_recommendations")

        # JWT (pour vérifier les tokens issus du backend principal)
        self.SECRET_KEY: str = os.getenv(
            "SECRET_KEY", "your-secret-key-change-this-in-production"
        )
        self.ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

        # CORS
        raw_origins = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
        )
        self.CORS_ORIGINS: list[str] = [o.strip() for o in raw_origins.split(",")]

        # Modèles ML — répertoire de sauvegarde des artefacts joblib
        self.MODEL_DIR: Path = BASE_DIR / os.getenv("MODEL_DIR", "artifacts")
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)

        # LLM (Ollama local ou Mistral Cloud API)
        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")  # "ollama" | "mistral"
        self.OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral")

        # Mistral Vision API
        self.MISTRAL_API_KEY: str = os.getenv("MISTRAL_API_KEY", "")
        self.MISTRAL_API_URL: str = "https://api.mistral.ai/v1/chat/completions"
        self.MISTRAL_MODEL: str = os.getenv("MISTRAL_MODEL", "pixtral-12b-2409")


settings = Settings()
