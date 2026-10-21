"""
Testes unitários e de integração para os modelos da camada Gold (Marts):
dim_anuncios_ativos e fct_metricas_bairro_diarias.
Valida definições SQL, integridade dos schemas YAML, criação das tabelas no PostgreSQL
e regras de negócio de métricas e detecção de oportunidades.
"""
from pathlib import Path
import unittest
import os
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = BASE_DIR / "dbt_imoveis"
MARTS_DIR = DBT_DIR / "models" / "marts"

load_dotenv(BASE_DIR / ".env")


class TestMartsModels(unittest.TestCase):
    """Valida especificações e dados dos modelos analíticos da camada Gold."""

    def test_sql_models_exist_and_syntax(self):
        """Valida a existência dos arquivos SQL e referências dbt."""
        dim_sql = MARTS_DIR / "dim_anuncios_ativos.sql"
        fct_sql = MARTS_DIR / "fct_metricas_bairro_diarias.sql"

        self.assertTrue(dim_sql.exists(), "dim_anuncios_ativos.sql deve existir.")
        self.assertTrue(fct_sql.exists(), "fct_metricas_bairro_diarias.sql deve existir.")

        dim_content = dim_sql.read_text(encoding="utf-8")
        self.assertIn("ref('int_anuncios_diarios')", dim_content)
        self.assertIn("ref('snp_historico_precos')", dim_content)
        self.assertIn("status_oportunidade", dim_content)
        self.assertIn("preco_m2_medio_bairro", dim_content)

        fct_content = fct_sql.read_text(encoding="utf-8")
        self.assertIn("ref('dim_anuncios_ativos')", fct_content)
        self.assertIn("PERCENTILE_CONT", fct_content)
        self.assertIn("total_anuncios_ativos", fct_content)

    def test_marts_yml_schema_tests(self):
        """Valida documentação e testes de schema em marts.yml."""
        yml_file = MARTS_DIR / "marts.yml"
        self.assertTrue(yml_file.exists(), "marts.yml deve existir.")

        with open(yml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        models = {m["name"]: m for m in data.get("models", [])}
        self.assertIn("dim_anuncios_ativos", models)
        self.assertIn("fct_metricas_bairro_diarias", models)

        # Checa constraints de dim_anuncios_ativos
        dim_cols = {c["name"]: c for c in models["dim_anuncios_ativos"].get("columns", [])}
        self.assertIn("surrogate_key", dim_cols)
        self.assertIn("unique", dim_cols["surrogate_key"].get("tests", []))
        self.assertIn("status_oportunidade", dim_cols)

        # Checa constraints de fct_metricas_bairro_diarias
        fct_cols = {c["name"]: c for c in models["fct_metricas_bairro_diarias"].get("columns", [])}
        self.assertIn("id_metrica", fct_cols)
        self.assertIn("unique", fct_cols["id_metrica"].get("tests", []))
        self.assertIn("preco_medio", fct_cols)
        self.assertIn("preco_mediano", fct_cols)

    def test_gold_tables_in_database(self):
        """Valida se as tabelas gold.dim_anuncios_ativos e gold.fct_metricas_bairro_diarias existem no Postgres."""
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
            # 1. Valida dim_anuncios_ativos
            cur.execute("""
                SELECT COUNT(*), COUNT(DISTINCT surrogate_key) 
                FROM gold.dim_anuncios_ativos;
            """)
            dim_total, dim_unique = cur.fetchone()
            self.assertGreater(dim_total, 0, "dim_anuncios_ativos deve conter registros.")
            self.assertEqual(dim_total, dim_unique, "surrogate_key deve ser estritamente única em dim_anuncios_ativos.")

            # Valida classificação de oportunidades
            cur.execute("""
                SELECT DISTINCT status_oportunidade 
                FROM gold.dim_anuncios_ativos;
            """)
            statuses = {r[0] for r in cur.fetchall()}
            self.assertTrue(statuses.issubset({"ABAIXO_DA_MEDIA", "REGULAR", "ACIMA_DA_MEDIA"}))

            # 2. Valida fct_metricas_bairro_diarias
            cur.execute("""
                SELECT 
                    COUNT(*),
                    MIN(preco_medio),
                    MIN(preco_mediano),
                    MIN(total_anuncios_ativos)
                FROM gold.fct_metricas_bairro_diarias;
            """)
            fct_total, min_avg, min_med, min_cnt = cur.fetchone()
            self.assertGreater(fct_total, 0, "fct_metricas_bairro_diarias deve conter métricas.")
            self.assertGreater(min_avg, 0, "Preço médio agregado deve ser positivo.")
            self.assertGreater(min_med, 0, "Preço mediano agregado deve ser positivo.")
            self.assertGreater(min_cnt, 0, "Total de anúncios ativos agregados deve ser positivo.")
        conn.close()


if __name__ == "__main__":
    unittest.main()
