"""
Gerenciamento de conexões assíncronas do SQLAlchemy 2.0.
Cria o AsyncEngine, AsyncSession maker e a injeção de dependência get_db.
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from api.core.config import settings

# Configuração do Engine Assíncrono com SSL para Neon Postgres
connect_args = {
    "timeout": 60,
    "command_timeout": 60,
}
if settings.POSTGRES_SSL:
    connect_args["ssl"] = settings.POSTGRES_SSL

from sqlalchemy.pool import NullPool

# Se o host configurado for o connection pooler da Neon (pgBouncer),
# a recomendação oficial da Neon é desativar o pool local do SQLAlchemy usando NullPool,
# evitando concorrência de pools e deadlocks de event loop assíncrono.
is_pooler = "-pooler" in settings.POSTGRES_HOST.lower()

engine_kwargs = {
    "connect_args": connect_args,
    "echo": settings.DEBUG,
}

if is_pooler:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 10,
        "max_overflow": 20,
    })

async_engine = create_async_engine(
    settings.async_database_url,
    **engine_kwargs,
)

# Fábrica de sessões assíncronas
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Base declarativa para os modelos ORM
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection do FastAPI para fornecer uma sessão assíncrona do banco de dados."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
