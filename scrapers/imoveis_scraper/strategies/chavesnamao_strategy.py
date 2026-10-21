"""
Estratégia de extração para o portal Chaves na Mão.
Processa listagens HTML e JSON-LD de imóveis, capturando anúncios de apartamentos.
"""
import re
from typing import Any, Dict, Generator, List, Optional
from loguru import logger
import scrapy
from scrapy.http import Request, Response

from imoveis_scraper.items import RawPropertyItem
from imoveis_scraper.strategies.base_strategy import BasePortalStrategy


class ChavesNaMaoStrategy(BasePortalStrategy):
    """
    Estratégia voltada ao portal Chaves na Mão.
    Extrai listagens HTML e metadados de anúncios imobiliários.
    """

    portal_name: str = "chaves_na_mao"

    default_neighborhoods: List[str] = [
        "sp-sao-paulo",
        "sp-sao-paulo-moema",
        "sp-sao-paulo-pinheiros",
        "sp-sao-paulo-itaim-bibi",
        "sp-sao-paulo-vila-mariana",
        "sp-sao-paulo-perdizes",
        "sp-sao-paulo-bela-vista",
        "sp-sao-paulo-tatuape",
        "sp-sao-paulo-santana",
    ]

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
        """Gera requisições para as rotas do Chaves na Mão."""
        route = "apartamentos-a-venda" if business_type.lower() in ["venda", "comprar", "compra"] else "apartamentos-para-alugar"
        target_locs = neighborhoods if neighborhoods else self.default_neighborhoods

        req_count = 0
        for loc in target_locs:
            if max_pages and req_count >= max_pages:
                logger.info(f"[{self.portal_name}] Limite max_pages={max_pages} atingido.")
                return

            slug = loc.strip().lower()
            if not slug.startswith(f"{state}-"):
                slug = f"{state}-{city}-{slug}"

            url = f"https://www.chavesnamao.com.br/{route}/{slug}/"
            req_count += 1
            yield Request(
                url=url,
                callback=spider.parse,
                meta={
                    "strategy": self,
                    "location_slug": slug,
                    "city": city,
                    "state": state,
                    "business_type": business_type,
                },
                errback=spider.handle_error,
                dont_filter=True,
            )

    def parse_response(
        self,
        spider: scrapy.Spider,
        response: Response,
    ) -> Generator[RawPropertyItem, None, None]:
        """Processa os links de anúncios presentes nas páginas de listagem do Chaves na Mão."""
        meta = response.meta
        city = meta.get("city", "sao-paulo").replace("-", " ").title()
        state = meta.get("state", "sp").upper()

        # Localiza links de imóveis no formato /imovel/.../id-12345/
        listing_links = set(re.findall(r'href="(/imovel/[^"]+/id-(\d+)/)"', response.text))

        if not listing_links:
            logger.info(f"[{self.portal_name}] Nenhum anúncio identificado em: {response.url}")
            return

        for path, listing_id in listing_links:
            str_id = str(listing_id).strip()
            if not str_id:
                continue

            seen_ids = getattr(spider, "seen_listing_ids", None)
            if seen_ids is not None:
                if str_id in seen_ids:
                    continue
                seen_ids.add(str_id)

            full_url = f"https://www.chavesnamao.com.br{path}"

            # Extração heurística rápida a partir do slug do anúncio
            # Ex: /imovel/apartamento-a-venda-3-quartos-com-garagem-sp-sao-paulo-belenzinho-RS500000/id-29817557/
            slug_lower = path.lower()
            
            # Preço extraído do slug (RS500000)
            price_match = re.search(r'rs(\d+)', slug_lower)
            price = float(price_match.group(1)) if price_match else None

            # Quartos
            bedrooms_match = re.search(r'(\d+)-quartos', slug_lower)
            bedrooms = int(bedrooms_match.group(1)) if bedrooms_match else None

            # Vagas
            has_garage = "garagem" in slug_lower
            parking_spots = 1 if has_garage else 0

            # Bairro aproximado
            bairro = "Desconhecido"
            bairro_match = re.search(r'sp-[a-z0-9\-]+-([a-z0-9\-]+)-rs', slug_lower)
            if bairro_match:
                bairro = bairro_match.group(1).replace("-", " ").title()

            payload: Dict[str, Any] = {
                "title": f"Apartamento com {bedrooms or 0} quartos em {bairro}",
                "price": price,
                "condo_fee": None,
                "iptu": None,
                "usable_area_m2": None,
                "bedrooms": bedrooms,
                "bathrooms": 1,
                "parking_spots": parking_spots,
                "address": {
                    "street": None,
                    "neighborhood": bairro,
                    "city": city,
                    "state": state,
                    "zip_code": None,
                    "latitude": None,
                    "longitude": None,
                },
                "amenities": ["GARAGEM"] if has_garage else [],
                "advertiser_type": "IMOBILIARIA",
                "raw": {
                    "id": str_id,
                    "url": full_url,
                    "path": path,
                },
            }

            yield self.build_raw_item(spider=spider, listing_id=str_id, url=full_url, payload=payload)
