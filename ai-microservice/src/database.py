"""
Connexions aux bases de données :
- PostgreSQL (lecture seule) : données utilisateurs issues du backend MSPR1
- MongoDB (lecture/écriture) : stockage des recommandations IA
"""
from typing import AsyncGenerator

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from src.config import settings

# ─────────────────────────────── PostgreSQL ────────────────────────────────
# Moteur SQLAlchemy synchrone (lecture seule des données métier)
pg_engine = create_engine(
    settings.POSTGRES_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
PGSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)
Base = declarative_base()


def get_pg_db() -> Session:
    """Dépendance FastAPI – session PostgreSQL."""
    db = PGSession()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────── MongoDB ───────────────────────────────────
_mongo_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(settings.MONGO_URL)
    return _mongo_client


def get_mongo_db() -> AsyncIOMotorDatabase:
    return get_mongo_client()[settings.MONGO_DB]


async def get_mongo() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    """Dépendance FastAPI – base MongoDB."""
    yield get_mongo_db()


async def close_mongo_connection() -> None:
    global _mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
