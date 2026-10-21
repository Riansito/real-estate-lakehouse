"""
Spider central unificado e adaptativo para coleta de anúncios de múltiplos portais imobiliários.
Utiliza o padrão Strategy para delegar o parsing específico a cada adaptador de portal,
compartilhando 100% da infraestrutura de governança, deduplicação, batch_id e envelope.
"""
from datetime import datetime, timezone
from typing import Any, Generator, List, Optional, Set, Union
import uuid

from loguru import logger
import scrapy
from scrapy import signals
from scrapy.http import Request, Response

from imoveis_scraper.items import RawPropertyItem
from imoveis_scraper.strategies import (
    BasePortalStrategy,
    get_all_strategies,
    get_strategy,
    list_supported_portals,
)


class ImoveisSpider(scrapy.Spider):
    """
    Spider Adaptativo Unificado de Imóveis.
    
    Exemplos de Uso:
    ----------------
    # 1. Coleta do QuintoAndar (padrão):
    scrapy crawl imoveis -a portal=quintoandar -a city=sao-paulo
    
    # 2. Coleta com limite de páginas para teste rápido:
    scrapy crawl imoveis -a portal=quintoandar -a max_pages=2 -a neighborhoods=moema
    
    # 3. Coleta de múltiplos portais simultaneamente:
    scrapy crawl imoveis -a portal=all -a max_pages=5
    """

    name = "imoveis"
    aliases = ["imoveis_spider"]
    allowed_domains = ["quintoandar.com.br", "chavesnamao.com.br"]

    custom_settings = {
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
    }

    def __init__(
        self,
        portal: str = "quintoandar",
        city: str = "sao-paulo",
        state: str = "sp",
        business_type: str = "venda",
        neighborhoods: Optional[str] = None,
        sub_filters: Optional[str] = None,
        max_pages: Optional[Union[int, str]] = None,
        batch_id: Optional[str] = None,
        scraped_at: Optional[str] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.portal_arg = portal.lower().strip()
        self.city = city.lower().strip()
        self.state = state.lower().strip()
        self.business_type = business_type.lower().strip()

        # Resolução das estratégias ativas
        if self.portal_arg in ["all", "todos", "*"]:
            self.strategies: List[BasePortalStrategy] = get_all_strategies()
        else:
            self.strategies = [get_strategy(self.portal_arg)]

        # Parâmetros opcionais de segmentação
        self.neighborhood_list = (
            [n.strip().lower() for n in neighborhoods.split(",") if n.strip()]
            if neighborhoods
            else None
        )
        self.sub_filter_list = (
            [f.strip() for f in sub_filters.split(",")]
            if sub_filters is not None
            else None
        )
        self.max_pages: Optional[int] = int(max_pages) if max_pages and int(max_pages) > 0 else None

        # Metadados de rastreabilidade
        self.batch_id: str = batch_id if batch_id else str(uuid.uuid4())
        self.scraped_at: str = (
            scraped_at if scraped_at else datetime.now(timezone.utc).isoformat()
        )

        # Controle de estado e métricas
        self.seen_listing_ids: Set[str] = set()
        self.pages_scraped_count: int = 0
        self.items_scraped_count: int = 0

        portal_names = [s.portal_name for s in self.strategies]
        logger.info(
            f"Spider Adaptativo '{self.name}' inicializado | Portais ativos: {portal_names} | "
            f"Cidade: {self.city}-{self.state} | Transação: {self.business_type} | "
            f"Batch ID: {self.batch_id} | Max Pages: {self.max_pages or 'ilimitado'}"
        )

    @classmethod
    def from_crawler(cls, crawler, *args: Any, **kwargs: Any):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    async def start(self):
        """Compatibilidade nativa com o reactor assincrono do Scrapy 2.13+."""
        for req in self.start_requests():
            yield req

    def start_requests(self) -> Generator[Request, None, None]:
        """Gera as requisições iniciais delegando a cada estratégia ativa."""
        for strategy in self.strategies:
            logger.info(f"Gerando requisições iniciais para estratégia: {strategy.portal_name}")
            yield from strategy.build_start_requests(
                spider=self,
                city=self.city,
                state=self.state,
                business_type=self.business_type,
                neighborhoods=self.neighborhood_list,
                sub_filters=self.sub_filter_list,
                max_pages=self.max_pages,
            )

    def parse(self, response: Response) -> Generator[RawPropertyItem, None, None]:
        """Processa a resposta delegando o parsing à estratégia associada à requisição."""
        strategy: Optional[BasePortalStrategy] = response.meta.get("strategy")
        if not strategy:
            logger.error(f"Nenhuma estratégia associada à requisição: {response.url}")
            return

        self.pages_scraped_count += 1
        logger.info(
            f"[{self.pages_scraped_count}] Processando ({strategy.portal_name}): {response.url}"
        )

        page_items = 0
        for item in strategy.parse_response(spider=self, response=response):
            self.items_scraped_count += 1
            page_items += 1
            yield item

        logger.info(
            f"Página finalizada ({strategy.portal_name}): {response.url} | "
            f"Novos anúncios: {page_items} | Total acumulado: {self.items_scraped_count}"
        )

    def handle_error(self, failure) -> None:
        """Tratamento centralizado de falhas de requisição de rede."""
        req_url = failure.request.url if hasattr(failure, "request") else "N/A"
        logger.error(f"Falha na requisição: {req_url} | Causa: {failure.value}")

    def spider_closed(self, spider: scrapy.Spider, reason: str) -> None:
        """Emite relatório estruturado de encerramento."""
        logger.info("=" * 70)
        logger.info(f"FINALIZAÇÃO DO SPIDER ADAPTATIVO: {spider.name}")
        logger.info(f"Motivo: {reason}")
        logger.info(f"Batch ID: {self.batch_id}")
        logger.info(f"Total de requisições processadas: {self.pages_scraped_count}")
        logger.info(f"Total de imóveis únicos coletados: {self.items_scraped_count}")
        logger.info("=" * 70)
