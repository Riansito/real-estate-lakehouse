"""
Endpoints de verificação de integridade e status da API.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from api.core.database import get_db
from api.core.config import settings

router = APIRouter(tags=["Health & Status"])


@router.get("/health", status_code=status.HTTP_200_OK, summary="Verificação de integridade do serviço e banco")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Verifica se a API está operacional e testa a conexão com o PostgreSQL Neon."""
    db_status = "unhealthy"
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_status = "healthy"
    except Exception as exc:
        db_status = f"error: {str(exc)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": settings.VERSION,
        "service": settings.PROJECT_NAME,
    }


@router.get("/", status_code=status.HTTP_200_OK, summary="Informações gerais da API")
async def root():
    """Retorna dados informativos da API do Data Lakehouse."""
    return {
        "message": f"Bem-vindo à {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "documentation": "/docs",
        "openapi_url": "/openapi.json",
        "endpoints": {
            "health": "/health",
            "imoveis": f"{settings.API_V1_STR}/imoveis",
            "oportunidades": f"{settings.API_V1_STR}/oportunidades",
            "metricas_bairros": f"{settings.API_V1_STR}/metricas/bairros",
        },
    }
