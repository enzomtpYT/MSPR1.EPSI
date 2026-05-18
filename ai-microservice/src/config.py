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

        # LLM (Ollama local ou Hugging Face Inference API)
        self.LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")  # "ollama" | "huggingface"
        self.OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral")
        self.HF_API_KEY: str = os.getenv("HF_API_KEY", "")
        self.HF_MODEL: str = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")


settings = Settings()
