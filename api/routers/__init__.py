"""Roteadores da API."""
from api.routers.health import router as health_router
from api.routers.imoveis import router as imoveis_router
from api.routers.analytics import router as analytics_router

__all__ = ["health_router", "imoveis_router", "analytics_router"]
