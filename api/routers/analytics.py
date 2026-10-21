"""
Endpoints analíticos da API:
- /historico-precos/{id}: Evolução temporal de preços (SCD Tipo 2)
- /metricas/bairros: Indicadores consolidados de mercado por bairro e data
- /oportunidades: Imóveis com alto desconto ou abaixo da média do bairro
"""
from math import ceil
from decimal import Decimal
from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, asc, desc

from api.core.database import get_db
from api.models.imoveis import DimAnuncioAtivo, FctMetricasBairroDiarias, SnpHistoricoPrecos
from api.schemas.imovel import ImovelResponse, PaginatedResponse
from api.schemas.metricas import MetricaBairroResponse
from api.schemas.historico import HistoricoPrecoResponse, HistoricoPrecoItem

router = APIRouter(tags=["Analytics & Oportunidades"])


@router.get(
    "/oportunidades",
    response_model=PaginatedResponse[ImovelResponse],
    status_code=status.HTTP_200_OK,
    summary="Listagem de imóveis com alto potencial de desconto (abaixo da média do bairro)",
)
async def list_oportunidades(
    bairro: Optional[str] = Query(None, description="Filtro por bairro (busca parcial case-insensitive)"),
    cidade: Optional[str] = Query(None, description="Filtro por cidade"),
    desconto_min_pct: Decimal = Query(
        Decimal("15.0"),
        ge=0,
        le=90,
        description="Percentual mínimo de desconto em relação à média do m² do bairro (padrão: 15%)",
    ),
    preco_max: Optional[Decimal] = Query(None, ge=0, description="Preço teto máximo de venda em Reais"),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna os apartamentos com melhor custo-benefício em relação à média do bairro.
    Filtra imóveis com status ABAIXO_DA_MEDIA ou cujo desvio seja menor ou igual a -desconto_min_pct.
    Ordena pelo maior desconto primeiro.
    """
    conditions = [
        DimAnuncioAtivo.diferenca_percentual_bairro <= -abs(desconto_min_pct)
    ]

    if bairro:
        conditions.append(DimAnuncioAtivo.bairro.ilike(f"%{bairro.strip().lower()}%"))

    if cidade:
        conditions.append(DimAnuncioAtivo.cidade.ilike(f"%{cidade.strip()}%"))

    if preco_max is not None:
        conditions.append(DimAnuncioAtivo.preco <= preco_max)

    where_clause = and_(*conditions)

    # 1. Total de oportunidades encontradas
    count_query = select(func.count(DimAnuncioAtivo.surrogate_key)).where(where_clause)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # 2. Busca paginada ordenada por maior desconto (diferenca_percentual_bairro ASC)
    offset_val = (page - 1) * page_size
    query = (
        select(DimAnuncioAtivo)
        .where(where_clause)
        .order_by(
            asc(DimAnuncioAtivo.diferenca_percentual_bairro),
            asc(DimAnuncioAtivo.preco),
            DimAnuncioAtivo.surrogate_key,
        )
        .offset(offset_val)
        .limit(page_size)
    )

    result = await db.execute(query)
    oportunidades = result.scalars().all()

    total_pages = ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=list(oportunidades),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/metricas/bairros",
    response_model=List[MetricaBairroResponse],
    status_code=status.HTTP_200_OK,
    summary="Métricas de preço e volume consolidadas por bairro",
)
async def list_metricas_bairros(
    cidade: Optional[str] = Query(None, description="Filtrar por cidade (ex: 'São Paulo')"),
    bairro: Optional[str] = Query(None, description="Filtrar por bairro (ex: 'moema')"),
    data_referencia: Optional[date] = Query(None, description="Filtrar por data específica (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna indicadores analíticos agregados pré-calculados:
    preço médio, mediana (P50), preço/m² médio e contagem de oportunidades.
    """
    conditions = []

    if cidade:
        conditions.append(FctMetricasBairroDiarias.cidade.ilike(f"%{cidade.strip()}%"))

    if bairro:
        conditions.append(FctMetricasBairroDiarias.bairro.ilike(f"%{bairro.strip().lower()}%"))

    if data_referencia:
        conditions.append(FctMetricasBairroDiarias.data_referencia == data_referencia)

    where_clause = and_(*conditions) if conditions else True

    query = (
        select(FctMetricasBairroDiarias)
        .where(where_clause)
        .order_by(
            asc(FctMetricasBairroDiarias.cidade),
            asc(FctMetricasBairroDiarias.bairro),
            desc(FctMetricasBairroDiarias.data_referencia),
        )
    )

    result = await db.execute(query)
    metricas = result.scalars().all()

    return list(metricas)


@router.get(
    "/historico-precos/{imovel_id}",
    response_model=HistoricoPrecoResponse,
    status_code=status.HTTP_200_OK,
    summary="Histórico temporal completo de alterações de preço de um imóvel",
)
async def get_historico_precos(
    imovel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna a linha do tempo completa de preços de venda, condomínio e IPTU
    registrados pelo dbt snapshot (SCD Tipo 2) para o anúncio especificado.
    Aceita surrogate_key ou portal_listing_id.
    """
    query = (
        select(SnpHistoricoPrecos)
        .where(
            or_(
                SnpHistoricoPrecos.surrogate_key == imovel_id.strip(),
                SnpHistoricoPrecos.portal_listing_id == imovel_id.strip(),
            )
        )
        .order_by(asc(SnpHistoricoPrecos.dbt_valid_from))
    )

    result = await db.execute(query)
    registros = result.scalars().all()

    if not registros:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Histórico de preços não encontrado para o imóvel '{imovel_id}'.",
        )

    # Constrói os itens enriquecidos com a flag is_current
    primeiro = registros[0]
    itens = [
        HistoricoPrecoItem(
            dbt_scd_id=r.dbt_scd_id,
            preco=r.preco,
            valor_condominio=r.valor_condominio,
            valor_iptu=r.valor_iptu,
            scraped_at=r.scraped_at,
            dbt_valid_from=r.dbt_valid_from,
            dbt_valid_to=r.dbt_valid_to,
            is_current=(r.dbt_valid_to is None),
        )
        for r in registros
    ]

    return HistoricoPrecoResponse(
        surrogate_key=primeiro.surrogate_key,
        source_portal=primeiro.source_portal,
        portal_listing_id=primeiro.portal_listing_id,
        total_alteracoes=len(itens),
        historico=itens,
    )
