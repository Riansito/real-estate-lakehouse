"""
Schemas Pydantic para validação e serialização de anúncios imobiliários.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Any, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict

T = TypeVar("T")


class ImovelBase(BaseModel):
    """Atributos fundamentais do imóvel."""
    model_config = ConfigDict(from_attributes=True)

    surrogate_key: str
    property_fingerprint: str
    source_portal: str
    portal_listing_id: str
    url: Optional[str] = None
    titulo: Optional[str] = None
    preco: Decimal
    valor_condominio: Optional[Decimal] = None
    valor_iptu: Optional[Decimal] = None
    area_util_m2: Optional[Decimal] = None
    preco_m2: Optional[Decimal] = None
    quartos: Optional[int] = None
    banheiros: int
    vagas: int
    rua: Optional[str] = None
    bairro: str
    bairro_raw: Optional[str] = None
    cidade: str
    estado: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    tipo_anunciante: Optional[str] = None
    status_oportunidade: str
    preco_m2_medio_bairro: Optional[Decimal] = None
    diferenca_percentual_bairro: Optional[Decimal] = None
    ultima_coleta: datetime
    preco_vigente_desde: datetime


class ImovelResponse(ImovelBase):
    """Modelo de retorno para listagens de imóveis."""
    pass


class ImovelDetailResponse(ImovelBase):
    """Modelo detalhado com comodidades completas."""
    comodidades: Optional[List[str]] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Envelope padrão de resposta paginada."""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
