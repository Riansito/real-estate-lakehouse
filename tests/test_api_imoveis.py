"""
Testes unitários e de integração para o endpoint GET /api/v1/imoveis (BACK-015).
Valida paginação, múltiplos filtros dinâmicos, ordenação e busca por ID.
"""
import asyncio
from pathlib import Path
import unittest
from httpx import AsyncClient, ASGITransport
from api.main import app


class TestApiImoveis(unittest.IsolatedAsyncioTestCase):
    """Testa endpoints da rota /api/v1/imoveis."""

    async def asyncSetUp(self):
        """Inicializa o cliente HTTP assíncrono para cada teste."""
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        """Fecha o cliente HTTP e libera o pool de conexões do event loop atual."""
        await self.client.aclose()
        from api.core.database import async_engine
        await async_engine.dispose()

    async def _get(self, url: str, max_retries: int = 3):
        """Helper com retry para tolerância a variações de latência em bancos de dados em nuvem."""
        for attempt in range(max_retries):
            try:
                return await self.client.get(url)
            except Exception:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1.0)

    async def test_list_imoveis_paginated_default(self):
        """Valida listagem padrão de imóveis com estrutura de paginação."""
        response = await self._get("/api/v1/imoveis")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("page", data)
        self.assertIn("page_size", data)
        self.assertIn("total_pages", data)

        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 20)
        self.assertGreater(data["total"], 0)
        self.assertLessEqual(len(data["items"]), 20)

    async def test_list_imoveis_filter_by_bairro(self):
        """Valida filtro dinâmico por bairro."""
        response = await self._get("/api/v1/imoveis?bairro=moema")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertGreater(data["total"], 0)
        for item in data["items"]:
            self.assertIn("moema", item["bairro"].lower())

    async def test_list_imoveis_filter_by_price_range(self):
        """Valida filtro de intervalo de preço (min e max)."""
        preco_min = 400000
        preco_max = 500000
        response = await self._get(f"/api/v1/imoveis?preco_min={preco_min}&preco_max={preco_max}")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertGreater(data["total"], 0)
        for item in data["items"]:
            preco = float(item["preco"])
            self.assertGreaterEqual(preco, preco_min)
            self.assertLessEqual(preco, preco_max)

    async def test_list_imoveis_filter_by_rooms_and_bathrooms(self):
        """Valida filtro por quartos e banheiros mínimos."""
        response = await self._get("/api/v1/imoveis?quartos_min=1&banheiros_min=1")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertGreater(data["total"], 0)
        for item in data["items"]:
            self.assertGreaterEqual(item["quartos"], 1)
            self.assertGreaterEqual(item["banheiros"], 1)

    async def test_list_imoveis_filter_by_opportunity_status(self):
        """Valida filtro por status de oportunidade."""
        response = await self._get("/api/v1/imoveis?status_oportunidade=ABAIXO_DA_MEDIA")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        for item in data["items"]:
            self.assertEqual(item["status_oportunidade"], "ABAIXO_DA_MEDIA")

    async def test_list_imoveis_ordering(self):
        """Valida ordenação por preço ascendente e descendente."""
        # ASC
        r_asc = await self._get("/api/v1/imoveis?order_by=preco&order_direction=asc&page_size=5")
        self.assertEqual(r_asc.status_code, 200)
        items_asc = r_asc.json()["items"]
        precos_asc = [float(i["preco"]) for i in items_asc]
        self.assertEqual(precos_asc, sorted(precos_asc))

        # DESC
        r_desc = await self._get("/api/v1/imoveis?order_by=preco&order_direction=desc&page_size=5")
        self.assertEqual(r_desc.status_code, 200)
        items_desc = r_desc.json()["items"]
        precos_desc = [float(i["preco"]) for i in items_desc]
        self.assertEqual(precos_desc, sorted(precos_desc, reverse=True))

    async def test_get_imovel_by_id_success(self):
        """Valida busca de detalhes de imóvel existente."""
        # Primeiro obtém um imóvel válido
        list_res = await self._get("/api/v1/imoveis?page_size=1")
        imovel_id = list_res.json()["items"][0]["surrogate_key"]

        # Busca pelo ID
        detail_res = await self._get(f"/api/v1/imoveis/{imovel_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertEqual(detail["surrogate_key"], imovel_id)
        self.assertIn("titulo", detail)
        self.assertIn("comodidades", detail)

    async def test_get_imovel_by_id_not_found(self):
        """Valida retorno de 404 quando o imóvel não existe."""
        detail_res = await self._get("/api/v1/imoveis/id_inexistente_999999")
        self.assertEqual(detail_res.status_code, 404)
        error = detail_res.json()
        self.assertIn("detail", error)


if __name__ == "__main__":
    unittest.main()
