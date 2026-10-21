"""
Aplicação Principal FastAPI do Lakehouse de Imóveis.
Expondo camadas de consumo e dados analíticos enriquecidos.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import text

from api.core.config import settings
from api.core.database import async_engine
from api.routers.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciador de ciclo de vida (startup e shutdown) da aplicação."""
    logger.info(f"Iniciando {settings.PROJECT_NAME} v{settings.VERSION}...")
    try:
        # Testa a conectividade com o banco de dados no startup
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Conexão assíncrona ao PostgreSQL estabelecida com sucesso! ✅")
    except Exception as exc:
        logger.warning(f"Não foi possível conectar ao banco no startup: {exc}")

    yield

    logger.info("Encerrando conexões do pool do banco de dados...")
    await async_engine.dispose()
    logger.info("Aplicação encerrada com sucesso! 🛑")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
API REST de alta performance para consulta do Data Lakehouse de Imóveis.
Permite listar anúncios de apartamentos com filtros dinâmicos, monitorar histórico
de alterações de preço (SCD Tipo 2) e identificar oportunidades de mercado.
    """,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configuração de CORS (Cross-Origin Resource Sharing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos Roteadores
app.include_router(health_router)
