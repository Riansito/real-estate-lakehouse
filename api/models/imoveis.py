"""
Modelos ORM do SQLAlchemy 2.0 mapeando as tabelas da camada Gold do Data Lakehouse.
Permite consultas tipadas e performáticas pela API FastAPI.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from sqlalchemy import (
    Column,
    String,
    Numeric,
    Integer,
    Float,
    DateTime,
    Date,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from api.core.database import Base


class DimAnuncioAtivo(Base):
    """Mapeamento da tabela dimensional gold.dim_anuncios_ativos."""

    __tablename__ = "dim_anuncios_ativos"
    __table_args__ = {"schema": "gold"}

    surrogate_key = Column(String(32), primary_key=True)
    property_fingerprint = Column(String(32), nullable=False, index=True)
    source_portal = Column(String(50), nullable=False)
    portal_listing_id = Column(String(100), nullable=False)
    batch_id = Column(String(100), nullable=False)
    url = Column(Text, nullable=True)
    titulo = Column(Text, nullable=True)
    preco = Column(Numeric(12, 2), nullable=False)
    valor_condominio = Column(Numeric(10, 2), nullable=True)
    valor_iptu = Column(Numeric(10, 2), nullable=True)
    area_util_m2 = Column(Numeric(8, 2), nullable=True)
    preco_m2 = Column(Numeric(12, 2), nullable=True)
    quartos = Column(Integer, nullable=True)
    banheiros = Column(Integer, nullable=False, default=1)
    vagas = Column(Integer, nullable=False, default=0)
    rua = Column(Text, nullable=True)
    bairro = Column(String(100), nullable=False, index=True)
    bairro_raw = Column(String(100), nullable=True)
    cidade = Column(String(100), nullable=False, index=True)
    estado = Column(String(10), nullable=True)
    cep = Column(String(20), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    comodidades = Column(JSONB, nullable=True)
    tipo_anunciante = Column(String(50), nullable=True)
    ultima_coleta = Column(DateTime(timezone=True), nullable=False)
    data_coleta = Column(Date, nullable=False)
    preco_vigente_desde = Column(DateTime(timezone=True), nullable=False)
    carregado_em = Column(DateTime(timezone=True), nullable=False)
    preco_m2_medio_bairro = Column(Numeric(12, 2), nullable=True)
    diferenca_percentual_bairro = Column(Numeric(6, 2), nullable=True)
    status_oportunidade = Column(String(30), nullable=False, index=True)


class FctMetricasBairroDiarias(Base):
    """Mapeamento da tabela de métricas analíticas agregadas gold.fct_metricas_bairro_diarias."""

    __tablename__ = "fct_metricas_bairro_diarias"
    __table_args__ = {"schema": "gold"}

    id_metrica = Column(String(32), primary_key=True)
    cidade = Column(String(100), nullable=False, index=True)
    bairro = Column(String(100), nullable=False, index=True)
    bairro_exibicao = Column(String(100), nullable=True)
    estado = Column(String(10), nullable=True)
    data_referencia = Column(Date, nullable=False, index=True)
    total_anuncios_ativos = Column(Integer, nullable=False)
    preco_medio = Column(Numeric(12, 2), nullable=False)
    preco_mediano = Column(Numeric(12, 2), nullable=False)
    preco_minimo = Column(Numeric(12, 2), nullable=True)
    preco_maximo = Column(Numeric(12, 2), nullable=True)
    preco_m2_medio = Column(Numeric(12, 2), nullable=True)
    preco_m2_mediano = Column(Numeric(12, 2), nullable=True)
    area_media_m2 = Column(Numeric(8, 2), nullable=True)
    quartos_medio = Column(Numeric(4, 1), nullable=True)
    total_oportunidades_abaixo_media = Column(Integer, nullable=False, default=0)
    atualizado_em = Column(DateTime(timezone=True), nullable=False)


class SnpHistoricoPrecos(Base):
    """Mapeamento da tabela histórica SCD Tipo 2 gold.snp_historico_precos."""

    __tablename__ = "snp_historico_precos"
    __table_args__ = {"schema": "gold"}

    dbt_scd_id = Column(String(32), primary_key=True)
    surrogate_key = Column(String(32), nullable=False, index=True)
    source_portal = Column(String(50), nullable=False)
    portal_listing_id = Column(String(100), nullable=False)
    preco = Column(Numeric(12, 2), nullable=False)
    valor_condominio = Column(Numeric(10, 2), nullable=True)
    valor_iptu = Column(Numeric(10, 2), nullable=True)
    scraped_at = Column(DateTime(timezone=True), nullable=False)
    dbt_updated_at = Column(DateTime(timezone=True), nullable=False)
    dbt_valid_from = Column(DateTime(timezone=True), nullable=False)
    dbt_valid_to = Column(DateTime(timezone=True), nullable=True)
