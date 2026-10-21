"""
Módulo de registro e resolução de estratégias de scraping para portais imobiliários.
Permite instanciar adaptadores dinamicamente através do nome ou slug do portal.
"""
from typing import Dict, List, Type

from imoveis_scraper.strategies.base_strategy import BasePortalStrategy
from imoveis_scraper.strategies.quintoandar_strategy import QuintoAndarStrategy
from imoveis_scraper.strategies.chavesnamao_strategy import ChavesNaMaoStrategy

# Registro de estratégias disponíveis
STRATEGY_REGISTRY: Dict[str, Type[BasePortalStrategy]] = {
    "quintoandar": QuintoAndarStrategy,
    "quinto_andar": QuintoAndarStrategy,
    "chavesnamao": ChavesNaMaoStrategy,
    "chaves_na_mao": ChavesNaMaoStrategy,
}


def get_strategy(portal_name: str) -> BasePortalStrategy:
    """
    Retorna a instância da estratégia correspondente ao nome do portal.
    Lança ValueError se o portal não for suportado.
    """
    key = portal_name.lower().strip()
    strategy_cls = STRATEGY_REGISTRY.get(key)
    if not strategy_cls:
        supported = ", ".join(sorted(set(STRATEGY_REGISTRY.keys())))
        raise ValueError(f"Portal '{portal_name}' não suportado. Portais disponíveis: {supported}")
    return strategy_cls()


def get_all_strategies() -> List[BasePortalStrategy]:
    """Retorna uma instância de cada estratégia única registrada."""
    unique_classes = set(STRATEGY_REGISTRY.values())
    return [cls() for cls in unique_classes]


def list_supported_portals() -> List[str]:
    """Retorna a lista ordenada dos nomes canônicos de portais suportados."""
    return sorted(list(set(s.portal_name for s in get_all_strategies())))
