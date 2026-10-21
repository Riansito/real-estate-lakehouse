"""
Testes unitários e de integração para os endpoints analíticos da API (BACK-016):
- GET /api/v1/oportunidades
- GET /api/v1/metricas/bairros
- GET /api/v1/historico-precos/{id}
"""
import asyncio
from pathlib import Path
import unittest
from httpx import AsyncClient, ASGITransport
from api.main import app


class TestApiAnalytics(unittest.IsolatedAsyncioTestCase):
    """Testa endpoints analíticos da rota /api/v1."""

    async def asyncSetUp(self):
        """Inicializa o cliente HTTP assíncrono para cada teste."""
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        """Fecha o cliente HTTP e libera as conexões do pool para o event loop atual."""
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

    async def test_get_oportunidades_default(self):
        """Valida listagem de oportunidades com ordenação por maior desconto."""
        response = await self._get("/api/v1/oportunidades")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertGreater(data["total"], 0)

        # Garante que os itens são ordenados pelo maior desconto (diferenca_percentual_bairro ASC)
        descontos = [float(item["diferenca_percentual_bairro"]) for item in data["items"] if item["diferenca_percentual_bairro"] is not None]
        self.assertEqual(descontos, sorted(descontos))
        for item in data["items"]:
            self.assertEqual(item["status_oportunidade"], "ABAIXO_DA_MEDIA")

    async def test_get_oportunidades_filters(self):
        """Valida filtros de bairro e desconto mínimo em /oportunidades."""
        response = await self._get("/api/v1/oportunidades?bairro=moema&desconto_min_pct=20.0")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        for item in data["items"]:
            self.assertIn("moema", item["bairro"].lower())
            self.assertLessEqual(float(item["diferenca_percentual_bairro"]), -20.0)

    async def test_get_metricas_bairros_list(self):
        """Valida listagem consolidada de métricas por bairro."""
        response = await self._get("/api/v1/metricas/bairros")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

        primeiro = data[0]
        self.assertIn("bairro", primeiro)
        self.assertIn("cidade", primeiro)
        self.assertIn("total_anuncios_ativos", primeiro)
        self.assertIn("preco_medio", primeiro)
        self.assertIn("preco_mediano", primeiro)
        self.assertIn("preco_m2_medio", primeiro)
        self.assertIn("total_oportunidades_abaixo_media", primeiro)

    async def test_get_metricas_bairros_filter(self):
        """Valida filtro por bairro em /metricas/bairros."""
        response = await self._get("/api/v1/metricas/bairros?bairro=moema")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertGreater(len(data), 0)
        for metrica in data:
            self.assertEqual(metrica["bairro"].lower(), "moema")

    async def test_get_historico_precos_success(self):
        """Valida busca do histórico SCD2 por surrogate_key e por portal_listing_id."""
        # 1. Obtém um anúncio ativo para teste
        list_res = await self._get("/api/v1/imoveis?page_size=1")
        anuncio = list_res.json()["items"][0]
        surrogate_key = anuncio["surrogate_key"]
        portal_listing_id = anuncio["portal_listing_id"]

        # 2. Busca por surrogate_key
        hist_res = await self._get(f"/api/v1/historico-precos/{surrogate_key}")
        self.assertEqual(hist_res.status_code, 200)
        hist_data = hist_res.json()

        self.assertEqual(hist_data["surrogate_key"], surrogate_key)
        self.assertEqual(hist_data["portal_listing_id"], portal_listing_id)
        self.assertGreater(hist_data["total_alteracoes"], 0)
        self.assertTrue(any(item["is_current"] for item in hist_data["historico"]))

        # 3. Busca por portal_listing_id
        hist_by_portal_res = await self._get(f"/api/v1/historico-precos/{portal_listing_id}")
        self.assertEqual(hist_by_portal_res.status_code, 200)
        self.assertEqual(hist_by_portal_res.json()["surrogate_key"], surrogate_key)

    async def test_get_historico_precos_not_found(self):
        """Valida 404 quando o histórico não existe para o identificador informado."""
        hist_res = await self._get("/api/v1/historico-precos/id_inexistente_123456")
        self.assertEqual(hist_res.status_code, 404)
        error = hist_res.json()
        self.assertIn("detail", error)


if __name__ == "__main__":
    unittest.main()
