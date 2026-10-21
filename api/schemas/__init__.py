"""Schemas Pydantic para validação e serialização da API."""
from api.schemas.imovel import (
    ImovelBase,
    ImovelResponse,
    ImovelDetailResponse,
    PaginatedResponse,
)
from api.schemas.metricas import MetricaBairroResponse
from api.schemas.historico import HistoricoPrecoItem, HistoricoPrecoResponse

__all__ = [
    "ImovelBase",
    "ImovelResponse",
    "ImovelDetailResponse",
    "PaginatedResponse",
    "MetricaBairroResponse",
    "HistoricoPrecoItem",
    "HistoricoPrecoResponse",
]
