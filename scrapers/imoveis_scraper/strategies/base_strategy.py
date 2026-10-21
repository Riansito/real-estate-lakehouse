"""
Interface base para estratégias de extração de portais imobiliários.
Define o contrato de métodos que cada adaptador específico de portal deve implementar.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Optional
import scrapy
from scrapy.http import Request, Response

from imoveis_scraper.items import RawPropertyItem


class BasePortalStrategy(ABC):
    """
    Classe base abstrata (Strategy Pattern) para extração de anúncios imobiliários.
    Cada portal (QuintoAndar, Chaves na Mão, Zap, etc.) deve implementar esta interface.
    """

    @property
    @abstractmethod
    def portal_name(self) -> str:
        """Identificador padronizado do portal (ex: 'quinto_andar', 'chaves_na_mao')."""
        pass

    @property
    @abstractmethod
    def default_neighborhoods(self) -> List[str]:
        """Lista padrão de bairros alvo para o portal caso nenhum seja fornecido."""
        pass

    @abstractmethod
    def build_start_requests(
        self,
        spider: scrapy.Spider,
        city: str,
        state: str,
        business_type: str,
        neighborhoods: Optional[List[str]] = None,
        sub_filters: Optional[List[str]] = None,
        max_pages: Optional[int] = None,
    ) -> Generator[Request, None, None]:
        """
        Gera as requisições HTTP iniciais específicas daquele portal (URLs de busca,
        rotas de bairros e filtros de tipologia).
        """
        pass

    @abstractmethod
    def parse_response(
        self,
        spider: scrapy.Spider,
        response: Response,
    ) -> Generator[RawPropertyItem, None, None]:
        """
        Processa a resposta HTTP do portal, extrai os imóveis presentes na página
        e retorna instâncias padronizadas de RawPropertyItem.
        """
        pass

    def build_raw_item(
        self,
        spider: scrapy.Spider,
        listing_id: str,
        url: str,
        payload: Dict[str, Any],
    ) -> RawPropertyItem:
        """
        Método utilitário para empacotar o anúncio no envelope padronizado de governança.
        """
        return RawPropertyItem(
            source_portal=self.portal_name,
            portal_listing_id=str(listing_id).strip(),
            scraped_at=getattr(spider, "scraped_at", None),
            batch_id=getattr(spider, "batch_id", None),
            url=url,
            payload=payload,
        )
