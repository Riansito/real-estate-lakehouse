"""
Testes unitários e de integração para a configuração da aplicação FastAPI (BACK-014).
Valida configurações, modelos ORM SQLAlchemy 2.0, schemas Pydantic e endpoints de health check.
"""
from pathlib import Path
import unittest
import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app
from api.core.config import settings
from api.models.imoveis import DimAnuncioAtivo, FctMetricasBairroDiarias, SnpHistoricoPrecos
from api.schemas.imovel import ImovelResponse, PaginatedResponse
from api.schemas.metricas import MetricaBairroResponse
from api.schemas.historico import HistoricoPrecoResponse


class TestApiSetup(unittest.IsolatedAsyncioTestCase):
    """Valida a infraestrutura básica e endpoints da aplicação FastAPI."""

    def test_settings_loaded(self):
        """Valida se as configurações básicas da API foram carregadas."""
        self.assertEqual(settings.PROJECT_NAME, "Real Estate Lakehouse API")
        self.assertEqual(settings.VERSION, "1.0.0")
        self.assertEqual(settings.API_V1_STR, "/api/v1")
        self.assertTrue(settings.async_database_url.startswith("postgresql+asyncpg://"))

    def test_orm_models_mapping(self):
        """Valida mapeamento das tabelas da camada Gold nos modelos SQLAlchemy."""
        self.assertEqual(DimAnuncioAtivo.__tablename__, "dim_anuncios_ativos")
        self.assertEqual(DimAnuncioAtivo.__table_args__["schema"], "gold")
        self.assertTrue(hasattr(DimAnuncioAtivo, "surrogate_key"))
        self.assertTrue(hasattr(DimAnuncioAtivo, "status_oportunidade"))

        self.assertEqual(FctMetricasBairroDiarias.__tablename__, "fct_metricas_bairro_diarias")
        self.assertEqual(FctMetricasBairroDiarias.__table_args__["schema"], "gold")
        self.assertTrue(hasattr(FctMetricasBairroDiarias, "preco_mediano"))

        self.assertEqual(SnpHistoricoPrecos.__tablename__, "snp_historico_precos")
        self.assertEqual(SnpHistoricoPrecos.__table_args__["schema"], "gold")
        self.assertTrue(hasattr(SnpHistoricoPrecos, "dbt_valid_to"))

    def test_schemas_pydantic_structure(self):
        """Valida conformidade e campos dos schemas Pydantic."""
        self.assertIn("surrogate_key", ImovelResponse.model_fields)
        self.assertIn("preco_m2", ImovelResponse.model_fields)
        self.assertIn("status_oportunidade", ImovelResponse.model_fields)

        self.assertIn("preco_mediano", MetricaBairroResponse.model_fields)
        self.assertIn("total_oportunidades_abaixo_media", MetricaBairroResponse.model_fields)

        self.assertIn("total_alteracoes", HistoricoPrecoResponse.model_fields)

    async def test_root_endpoint(self):
        """Valida se o endpoint GET / retorna as informações e links da API."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("message", data)
            self.assertIn("documentation", data)
            self.assertEqual(data["documentation"], "/docs")

    async def test_health_check_endpoint(self):
        """Valida se o endpoint GET /health conecta ao banco de dados com sucesso."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn("status", data)
            self.assertIn("database", data)
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["database"], "healthy")


if __name__ == "__main__":
    unittest.main()
