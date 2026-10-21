"""
Estratégia de extração para o portal QuintoAndar.
Processa páginas renderizadas em Next.js (SSR), extraindo o dicionário 'houses' dentro do script '__NEXT_DATA__'.
"""
import json
import re
from typing import Any, Dict, Generator, List, Optional
from loguru import logger
import scrapy
from scrapy.http import Request, Response

from imoveis_scraper.items import RawPropertyItem
from imoveis_scraper.strategies.base_strategy import BasePortalStrategy


class QuintoAndarStrategy(BasePortalStrategy):
    """
    Estratégia voltada ao portal QuintoAndar.
    Explora as rotas de busca de compra e locação desdobradas por bairros e tipologia de quartos.
    """

    portal_name: str = "quinto_andar"

    default_neighborhoods: List[str] = [
        "moema",
        "pinheiros",
        "itaim-bibi",
        "vila-mariana",
        "perdizes",
        "bela-vista",
        "santana",
        "tatuape",
        "brooklin",
        "consolacao",
        "jardins",
        "morumbi",
        "vila-madalena",
        "saude",
        "ipiranga",
        "butanta",
        "paraiso",
        "aclimacao",
        "cambuci",
        "campo-belo",
        "vila-olimpia",
        "higienopolis",
    ]

    default_sub_filters: List[str] = [
        "",                 # Destaques / principais
        "1-quartos",        # 1 quarto / studio
        "2-quartos",        # 2 quartos
        "3-quartos",        # 3 quartos
        "4-mais-quartos",   # 4 ou mais quartos
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
        """Gera requisições HTTP para as rotas do QuintoAndar."""
        # Mapeia tipo de negócio para rota na URL do QuintoAndar
        route = "comprar" if business_type.lower() in ["venda", "comprar", "compra"] else "alugar"
        target_neighborhoods = neighborhoods if neighborhoods else self.default_neighborhoods
        target_filters = sub_filters if sub_filters is not None else self.default_sub_filters

        req_count = 0
        for neighborhood in target_neighborhoods:
            for sub_filter in target_filters:
                if max_pages and req_count >= max_pages:
                    logger.info(f"[{self.portal_name}] Limite max_pages={max_pages} atingido.")
                    return

                loc_slug = f"{neighborhood}-{city}-{state}-brasil"
                if sub_filter:
                    url = f"https://www.quintoandar.com.br/{route}/imovel/{loc_slug}/{sub_filter}"
                else:
                    url = f"https://www.quintoandar.com.br/{route}/imovel/{loc_slug}"

                req_count += 1
                yield Request(
                    url=url,
                    callback=spider.parse,
                    meta={
                        "strategy": self,
                        "neighborhood": neighborhood,
                        "sub_filter": sub_filter,
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
        """Extrai anúncios do JSON __NEXT_DATA__ da resposta HTML do QuintoAndar."""
        meta = response.meta
        fallback_neighborhood = meta.get("neighborhood", "")
        city = meta.get("city", "sao-paulo").replace("-", " ").title()
        state = meta.get("state", "sp").upper()
        biz_type = meta.get("business_type", "venda").lower()

        # 1. Localiza o script __NEXT_DATA__
        next_data_json: Optional[str] = None
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', response.text)
        if match:
            next_data_json = match.group(1)
        else:
            xpath_match = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
            if xpath_match:
                next_data_json = xpath_match

        if not next_data_json:
            logger.warning(f"[{self.portal_name}] __NEXT_DATA__ não encontrado em: {response.url}")
            return

        try:
            data = json.loads(next_data_json)
        except json.JSONDecodeError as err:
            logger.error(f"[{self.portal_name}] Erro ao decodificar JSON em {response.url}: {err}")
            return

        initial_state = data.get("props", {}).get("pageProps", {}).get("initialState", {})
        houses: Dict[str, Any] = initial_state.get("houses", {})

        if not houses:
            logger.info(f"[{self.portal_name}] Nenhum imóvel retornado para {response.url}")
            return

        for house_id, house in houses.items():
            if not isinstance(house, dict):
                continue

            str_id = str(house_id).strip()
            if not str_id:
                continue

            # Deduplicação no spider
            seen_ids = getattr(spider, "seen_listing_ids", None)
            if seen_ids is not None:
                if str_id in seen_ids:
                    continue
                seen_ids.add(str_id)

            item = self._build_item(
                spider=spider,
                house_id=str_id,
                house=house,
                fallback_neighborhood=fallback_neighborhood,
                city=city,
                state=state,
                business_type=biz_type,
            )
            if item:
                yield item

    def _build_item(
        self,
        spider: scrapy.Spider,
        house_id: str,
        house: Dict[str, Any],
        fallback_neighborhood: str,
        city: str,
        state: str,
        business_type: str,
    ) -> Optional[RawPropertyItem]:
        """Normaliza os campos para o contrato DW e encapsula o envelope."""
        try:
            sale_price = house.get("salePrice")
            rent_price = house.get("rentPrice")

            if business_type in ["venda", "comprar", "compra"]:
                price_val = sale_price if sale_price is not None else rent_price
            else:
                price_val = rent_price if rent_price is not None else sale_price

            price = float(price_val) if price_val is not None else None

            condo_iptu = house.get("condoIptu")
            condo_fee = float(condo_iptu) if condo_iptu is not None else None

            area_val = house.get("area")
            usable_area_m2 = float(area_val) if area_val is not None else None

            bedrooms_val = house.get("bedrooms")
            bedrooms = int(bedrooms_val) if bedrooms_val is not None else None

            bathrooms_val = house.get("bathrooms")
            bathrooms = int(bathrooms_val) if bathrooms_val is not None else None

            parking_val = house.get("parkingSpots")
            parking_spots = int(parking_val) if parking_val is not None else None

            address_info = house.get("address") or {}
            street = address_info.get("address") if isinstance(address_info, dict) else None
            addr_city = (
                address_info.get("city")
                if isinstance(address_info, dict) and address_info.get("city")
                else city
            )
            bairro = (
                house.get("neighbourhood")
                or house.get("regionName")
                or fallback_neighborhood.replace("-", " ").title()
            )

            amenities = sorted(
                list(set(list(house.get("amenities") or []) + list(house.get("installations") or [])))
            )
            short_desc = house.get("shortSaleDescription") or house.get("shortRentDescription")
            prop_type = house.get("type", "Apartamento")
            title = short_desc if short_desc else f"{prop_type} com {bedrooms or 0} quartos em {bairro}"

            payload: Dict[str, Any] = {
                "title": title,
                "price": price,
                "condo_fee": condo_fee,
                "iptu": None,
                "usable_area_m2": usable_area_m2,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "parking_spots": parking_spots,
                "address": {
                    "street": street,
                    "neighborhood": bairro,
                    "city": addr_city,
                    "state": state,
                    "zip_code": None,
                    "latitude": None,
                    "longitude": None,
                },
                "amenities": amenities,
                "advertiser_type": "IMOBILIARIA",
                "raw": house,
            }

            url = f"https://www.quintoandar.com.br/imovel/{house_id}"
            return self.build_raw_item(spider=spider, listing_id=house_id, url=url, payload=payload)
        except Exception as err:
            logger.error(f"[{self.portal_name}] Erro ao processar imóvel {house_id}: {err}")
            return None
