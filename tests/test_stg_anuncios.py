"""
Testes unitários e de integração para o modelo de staging stg_anuncios no dbt.
Valida arquivos de especificação (sources.yml, stg_anuncios.sql, stg_anuncios.yml)
e integridade da view relacional gerada no banco de dados.
"""
from pathlib import Path
import unittest
import os
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = BASE_DIR / "dbt_imoveis"
STAGING_DIR = DBT_DIR / "models" / "staging"

load_dotenv(BASE_DIR / ".env")


class TestStgAnuncios(unittest.TestCase):
    """Valida especificações e comportamento do modelo stg_anuncios."""

    def test_sources_yml_exists_and_valid(self):
        """Valida se sources.yml declara corretamente a fonte raw.landing_anuncios."""
        source_file = STAGING_DIR / "sources.yml"
        self.assertTrue(source_file.exists(), "sources.yml deve existir.")

        with open(source_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        sources = data.get("sources", [])
        raw_source = next((s for s in sources if s.get("name") == "raw"), None)
        self.assertIsNotNone(raw_source, "Fonte 'raw' deve estar presente em sources.yml.")
        self.assertEqual(raw_source.get("schema"), "raw")

        tables = raw_source.get("tables", [])
        landing_tbl = next((t for t in tables if t.get("name") == "landing_anuncios"), None)
        self.assertIsNotNone(landing_tbl, "Tabela 'landing_anuncios' deve estar declarada na fonte raw.")

    def test_stg_anuncios_sql_syntax_and_fields(self):
        """Valida se stg_anuncios.sql referencia a fonte e extrai os campos esperados."""
        sql_file = STAGING_DIR / "stg_anuncios.sql"
        self.assertTrue(sql_file.exists(), "stg_anuncios.sql deve existir.")

        content = sql_file.read_text(encoding="utf-8")
        self.assertIn("{{ source('raw', 'landing_anuncios') }}", content)
        self.assertIn("materialized='view'", content)

        # Campos obrigatórios extraídos
        expected_fields = [
            "landing_id",
            "source_portal",
            "portal_listing_id",
            "scraped_at",
            "batch_id",
            "url",
            "titulo",
            "preco",
            "valor_condominio",
            "valor_iptu",
            "area_util_m2",
            "quartos",
            "banheiros",
            "vagas",
            "rua",
            "bairro",
            "cidade",
            "estado",
            "cep",
            "latitude",
            "longitude",
            "comodidades",
            "tipo_anunciante",
            "carregado_em",
        ]
        for field in expected_fields:
            self.assertIn(field, content, f"Campo {field} deve estar presente em stg_anuncios.sql")

    def test_stg_anuncios_yml_schema_tests(self):
        """Valida se stg_anuncios.yml possui a documentação e os testes de qualidade."""
        yml_file = STAGING_DIR / "stg_anuncios.yml"
        self.assertTrue(yml_file.exists(), "stg_anuncios.yml deve existir.")

        with open(yml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        models = data.get("models", [])
        stg_model = next((m for m in models if m.get("name") == "stg_anuncios"), None)
        self.assertIsNotNone(stg_model, "Modelo 'stg_anuncios' deve estar definido em stg_anuncios.yml")

        columns = {c["name"]: c for c in stg_model.get("columns", [])}
        self.assertIn("landing_id", columns)
        self.assertIn("unique", columns["landing_id"].get("tests", []))
        self.assertIn("not_null", columns["landing_id"].get("tests", []))
        self.assertIn("not_null", columns["source_portal"].get("tests", []))
        self.assertIn("not_null", columns["portal_listing_id"].get("tests", []))

    def test_staging_view_in_database(self):
        """Valida se a view staging.stg_anuncios está acessível no banco de dados se configurado."""
        if not os.getenv("POSTGRES_HOST") or not os.getenv("POSTGRES_PASSWORD"):
            self.skipTest("Variáveis de ambiente do PostgreSQL não configuradas.")

        import psycopg
        conn = psycopg.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT", 5432),
            connect_timeout=10,
        )
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.views 
                WHERE table_schema = 'staging' AND table_name = 'stg_anuncios';
            """)
            row = cur.fetchone()
            self.assertIsNotNone(row, "View staging.stg_anuncios deve existir no banco de dados.")

            # Valida query de leitura
            cur.execute("SELECT COUNT(*) FROM staging.stg_anuncios;")
            count = cur.fetchone()[0]
            self.assertGreaterEqual(count, 0, "A view stg_anuncios deve ser consultável.")
        conn.close()


if __name__ == "__main__":
    unittest.main()
