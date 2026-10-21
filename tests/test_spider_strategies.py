"""
Testes unitários para as estratégias de extração e o spider adaptativo de imóveis.
Valida o contrato de dados, a geração de requisições e a integridade do envelope RawPropertyItem.
"""
import json
import sys
from pathlib import Path
import unittest

# Adiciona scrapers ao path para importação direta
scrapers_dir = Path(__file__).resolve().parent.parent / "scrapers"
if str(scrapers_dir) not in sys.path:
    sys.path.insert(0, str(scrapers_dir))

from scrapy.http import HtmlResponse, Request

from imoveis_scraper.items import RawPropertyItem
from imoveis_scraper.spiders.imoveis_spider import ImoveisSpider
from imoveis_scraper.strategies import (
    ChavesNaMaoStrategy,
    QuintoAndarStrategy,
    get_all_strategies,
    get_strategy,
    list_supported_portals,
)


class TestStrategyRegistry(unittest.TestCase):
    """Testes para o registro central de estratégias."""

    def test_get_strategy_quintoandar(self):
        strategy = get_strategy("quintoandar")
        self.assertIsInstance(strategy, QuintoAndarStrategy)
        self.assertEqual(strategy.portal_name, "quinto_andar")

    def test_get_strategy_chavesnamao(self):
        strategy = get_strategy("chavesnamao")
        self.assertIsInstance(strategy, ChavesNaMaoStrategy)
        self.assertEqual(strategy.portal_name, "chaves_na_mao")

    def test_get_strategy_invalid(self):
        with self.assertRaises(ValueError):
            get_strategy("portal_inexistente")

    def test_list_supported_portals(self):
        portals = list_supported_portals()
        self.assertIn("quinto_andar", portals)
        self.assertIn("chaves_na_mao", portals)


class TestQuintoAndarStrategy(unittest.TestCase):
    """Testes de geração de requisições e parsing do QuintoAndar."""

    def setUp(self):
        self.strategy = QuintoAndarStrategy()
        self.spider = ImoveisSpider(portal="quintoandar", batch_id="test-batch-uuid")

    def test_build_start_requests(self):
        requests = list(
            self.strategy.build_start_requests(
                spider=self.spider,
                city="sao-paulo",
                state="sp",
                business_type="venda",
                neighborhoods=["moema"],
                sub_filters=["1-quartos"],
            )
        )
        self.assertEqual(len(requests), 1)
        req = requests[0]
        expected_url = "https://www.quintoandar.com.br/comprar/imovel/moema-sao-paulo-sp-brasil/1-quartos"
        self.assertEqual(req.url, expected_url)

    def test_parse_response_success(self):
        mock_next_data = {
            "props": {
                "pageProps": {
                    "initialState": {
                        "houses": {
                            "894101874": {
                                "id": "894101874",
                                "type": "Apartamento",
                                "salePrice": 450000,
                                "rentPrice": 2000,
                                "condoIptu": 600,
                                "area": 55,
                                "bedrooms": 2,
                                "bathrooms": 1,
                                "parkingSpots": 1,
                                "address": {"address": "Rua das Flores", "city": "São Paulo"},
                                "neighbourhood": "Moema",
                                "amenities": ["PISCINA"],
                                "installations": ["ACADEMIA"],
                            }
                        }
                    }
                }
            }
        }
        html = f"""
        <html>
            <head>
                <script id="__NEXT_DATA__" type="application/json">
                    {json.dumps(mock_next_data)}
                </script>
            </head>
            <body>Mock Page</body>
        </html>
        """
        request = Request(
            url="https://www.quintoandar.com.br/comprar/imovel/moema-sao-paulo-sp-brasil",
            meta={
                "strategy": self.strategy,
                "neighborhood": "moema",
                "city": "sao-paulo",
                "state": "sp",
                "business_type": "venda",
            },
        )
        response = HtmlResponse(
            url=request.url,
            body=html.encode("utf-8"),
            encoding="utf-8",
            request=request,
        )

        items = list(self.strategy.parse_response(spider=self.spider, response=response))
        self.assertEqual(len(items), 1)
        item: RawPropertyItem = items[0]

        # Valida envelope
        self.assertEqual(item["source_portal"], "quinto_andar")
        self.assertEqual(item["portal_listing_id"], "894101874")
        self.assertEqual(item["batch_id"], "test-batch-uuid")
        self.assertEqual(item["url"], "https://www.quintoandar.com.br/imovel/894101874")

        # Valida payload interno
        payload = item["payload"]
        self.assertEqual(payload["price"], 450000.0)
        self.assertEqual(payload["condo_fee"], 600.0)
        self.assertEqual(payload["usable_area_m2"], 55.0)
        self.assertEqual(payload["bedrooms"], 2)
        self.assertEqual(payload["bathrooms"], 1)
        self.assertEqual(payload["parking_spots"], 1)
        self.assertEqual(payload["address"]["neighborhood"], "Moema")
        self.assertEqual(payload["address"]["street"], "Rua das Flores")
        self.assertIn("PISCINA", payload["amenities"])
        self.assertIn("ACADEMIA", payload["amenities"])


class TestChavesNaMaoStrategy(unittest.TestCase):
    """Testes para a estratégia Chaves na Mão."""

    def setUp(self):
        self.strategy = ChavesNaMaoStrategy()
        self.spider = ImoveisSpider(portal="chavesnamao", batch_id="test-batch-cm")

    def test_parse_response_extracts_links(self):
        html = """
        <html>
            <body>
                <a href="/imovel/apartamento-a-venda-2-quartos-com-garagem-sp-sao-paulo-moema-RS600000/id-11223344/">Link 1</a>
                <a href="/imovel/apartamento-a-venda-3-quartos-com-garagem-sp-sao-paulo-pinheiros-RS850000/id-55667788/">Link 2</a>
            </body>
        </html>
        """
        request = Request(
            url="https://www.chavesnamao.com.br/apartamentos-a-venda/sp-sao-paulo/",
            meta={
                "strategy": self.strategy,
                "city": "sao-paulo",
                "state": "sp",
                "business_type": "venda",
            },
        )
        response = HtmlResponse(
            url=request.url,
            body=html.encode("utf-8"),
            encoding="utf-8",
            request=request,
        )

        items = list(self.strategy.parse_response(spider=self.spider, response=response))
        self.assertEqual(len(items), 2)
        listing_ids = {it["portal_listing_id"] for it in items}
        self.assertIn("11223344", listing_ids)
        self.assertIn("55667788", listing_ids)


if __name__ == "__main__":
    unittest.main()
