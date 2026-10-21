"""
Endpoints de consulta e listagem de imóveis (anúncios ativos).
Oferece paginação de alta performance e filtros dinâmicos combinados.
"""
from math import ceil
from decimal import Decimal
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, asc, desc

from api.core.database import get_db
from api.models.imoveis import DimAnuncioAtivo
from api.schemas.imovel import ImovelResponse, ImovelDetailResponse, PaginatedResponse

router = APIRouter(prefix="/imoveis", tags=["Imóveis"])


@router.get(
    "",
    response_model=PaginatedResponse[ImovelResponse],
    status_code=status.HTTP_200_OK,
    summary="Listagem paginada de imóveis com filtros dinâmicos",
)
async def list_imoveis(
    bairro: Optional[str] = Query(None, description="Nome do bairro (busca parcial case-insensitive, ex: 'moema')"),
    cidade: Optional[str] = Query(None, description="Cidade do imóvel (ex: 'São Paulo')"),
    preco_min: Optional[Decimal] = Query(None, ge=0, description="Preço mínimo de venda em Reais"),
    preco_max: Optional[Decimal] = Query(None, ge=0, description="Preço máximo de venda em Reais"),
    area_min: Optional[Decimal] = Query(None, ge=0, description="Área útil privativa mínima em m²"),
    area_max: Optional[Decimal] = Query(None, ge=0, description="Área útil privativa máxima em m²"),
    quartos_min: Optional[int] = Query(None, ge=0, description="Número mínimo de quartos"),
    banheiros_min: Optional[int] = Query(None, ge=1, description="Número mínimo de banheiros"),
    vagas_min: Optional[int] = Query(None, ge=0, description="Número mínimo de vagas de garagem"),
    status_oportunidade: Optional[str] = Query(
        None,
        description="Filtro por status de oportunidade ('ABAIXO_DA_MEDIA', 'REGULAR', 'ACIMA_DA_MEDIA')",
    ),
    source_portal: Optional[str] = Query(None, description="Portal de origem (ex: 'quinto_andar', 'chaves_na_mao')"),
    order_by: str = Query(
        "preco",
        description="Campo de ordenação ('preco', 'preco_m2', 'area_util_m2', 'ultima_coleta')",
    ),
    order_direction: str = Query("asc", description="Direção da ordenação ('asc' ou 'desc')"),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Quantidade de itens por página (máx: 100)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna catálogo paginado de imóveis ativos no Lakehouse.
    Permite combinar múltiplos filtros para busca precisa.
    """
    # Construção dinâmica da cláusula WHERE
    conditions = []

    if bairro:
        conditions.append(DimAnuncioAtivo.bairro.ilike(f"%{bairro.strip().lower()}%"))

    if cidade:
        conditions.append(DimAnuncioAtivo.cidade.ilike(f"%{cidade.strip()}%"))

    if preco_min is not None:
        conditions.append(DimAnuncioAtivo.preco >= preco_min)

    if preco_max is not None:
        conditions.append(DimAnuncioAtivo.preco <= preco_max)

    if area_min is not None:
        conditions.append(DimAnuncioAtivo.area_util_m2 >= area_min)

    if area_max is not None:
        conditions.append(DimAnuncioAtivo.area_util_m2 <= area_max)

    if quartos_min is not None:
        conditions.append(DimAnuncioAtivo.quartos >= quartos_min)

    if banheiros_min is not None:
        conditions.append(DimAnuncioAtivo.banheiros >= banheiros_min)

    if vagas_min is not None:
        conditions.append(DimAnuncioAtivo.vagas >= vagas_min)

    if status_oportunidade:
        conditions.append(DimAnuncioAtivo.status_oportunidade == status_oportunidade.strip().upper())

    if source_portal:
        conditions.append(DimAnuncioAtivo.source_portal == source_portal.strip().lower())

    where_clause = and_(*conditions) if conditions else True

    # 1. Contagem total de itens correspondentes
    count_query = select(func.count(DimAnuncioAtivo.surrogate_key)).where(where_clause)
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # 2. Ordenação
    order_col_map = {
        "preco": DimAnuncioAtivo.preco,
        "preco_m2": DimAnuncioAtivo.preco_m2,
        "area_util_m2": DimAnuncioAtivo.area_util_m2,
        "ultima_coleta": DimAnuncioAtivo.ultima_coleta,
    }
    target_col = order_col_map.get(order_by.lower(), DimAnuncioAtivo.preco)
    order_func = desc if order_direction.lower() == "desc" else asc

    # 3. Paginação com offset e limit
    offset_val = (page - 1) * page_size
    query = (
        select(DimAnuncioAtivo)
        .where(where_clause)
        .order_by(order_func(target_col), DimAnuncioAtivo.surrogate_key)
        .offset(offset_val)
        .limit(page_size)
    )

    result = await db.execute(query)
    imoveis = result.scalars().all()

    total_pages = ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse(
        items=list(imoveis),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{imovel_id}",
    response_model=ImovelDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Detalhes completos de um imóvel específico",
)
async def get_imovel_by_id(
    imovel_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna os detalhes completos de um imóvel pelo seu surrogate_key (MD5)
    ou pelo portal_listing_id original.
    """
    query = select(DimAnuncioAtivo).where(
        or_(
            DimAnuncioAtivo.surrogate_key == imovel_id.strip(),
            DimAnuncioAtivo.portal_listing_id == imovel_id.strip(),
        )
    )
    result = await db.execute(query)
    imovel = result.scalar_one_or_none()

    if not imovel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imóvel com identificador '{imovel_id}' não encontrado no catálogo.",
        )

    return imovel
