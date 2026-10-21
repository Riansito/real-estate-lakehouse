"""
Schemas Pydantic para indicadores de mercado e agregações por bairro.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class MetricaBairroResponse(BaseModel):
    """Métricas de preço e volume consolidadas por bairro."""
    model_config = ConfigDict(from_attributes=True)

    id_metrica: str
    cidade: str
    bairro: str
    bairro_exibicao: Optional[str] = None
    estado: Optional[str] = None
    data_referencia: date
    total_anuncios_ativos: int
    preco_medio: Decimal
    preco_mediano: Decimal
    preco_minimo: Optional[Decimal] = None
    preco_maximo: Optional[Decimal] = None
    preco_m2_medio: Optional[Decimal] = None
    preco_m2_mediano: Optional[Decimal] = None
    area_media_m2: Optional[Decimal] = None
    quartos_medio: Optional[Decimal] = None
    total_oportunidades_abaixo_media: int
    atualizado_em: datetime
