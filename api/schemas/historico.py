"""
Schemas Pydantic para histórico de preços e taxas (SCD Tipo 2).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class HistoricoPrecoItem(BaseModel):
    """Ponto temporal de preço no histórico de um imóvel."""
    model_config = ConfigDict(from_attributes=True)

    dbt_scd_id: str
    preco: Decimal
    valor_condominio: Optional[Decimal] = None
    valor_iptu: Optional[Decimal] = None
    scraped_at: datetime
    dbt_valid_from: datetime
    dbt_valid_to: Optional[datetime] = None
    is_current: bool = False


class HistoricoPrecoResponse(BaseModel):
    """Resposta com lista de variações temporais de preço de um imóvel."""
    surrogate_key: str
    source_portal: str
    portal_listing_id: str
    total_alteracoes: int
    historico: List[HistoricoPrecoItem]
