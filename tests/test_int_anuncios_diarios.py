"""
Testes unitários e de integração para o modelo intermediate int_anuncios_diarios.
Valida regras de saneamento, deduplicação de coleta (Nível 1), chave substituta (surrogate key)
e fingerprint canônico de entidade (Nível 2).
"""
from pathlib import Path
import unittest
import os
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = BASE_DIR / "dbt_imoveis"
INTERMEDIATE_DIR = DBT_DIR / "models" / "intermediate"

load_dotenv(BASE_DIR / ".env")


class TestIntAnunciosDiarios(unittest.TestCase):
    """Valida especificações e comportamento do modelo int_anuncios_diarios."""

    def test_sql_model_exists_and_syntax(self):
        """Valida existência do modelo SQL e presença dos elementos-chave de saneamento e dedup."""
        sql_file = INTERMEDIATE_DIR / "int_anuncios_diarios.sql"
        self.assertTrue(sql_file.exists(), "int_anuncios_diarios.sql deve existir.")

        content = sql_file.read_text(encoding="utf-8")
        self.assertIn("ref('stg_anuncios')", content)
        self.assertIn("ROW_NUMBER() OVER", content)
        self.assertIn("PARTITION BY source_portal, portal_listing_id, data_coleta", content)
        self.assertIn("MD5(source_portal || '-' || portal_listing_id)", content)
        self.assertIn("property_fingerprint", content)
        self.assertIn("preco_m2", content)
        self.assertIn("TRANSLATE", content)

    def test_schema_yml_exists_and_tests(self):
        """Valida se o schema YAML possui a documentação e os testes de qualidade obrigatórios."""
        yml_file = INTERMEDIATE_DIR / "int_anuncios_diarios.yml"
        self.assertTrue(yml_file.exists(), "int_anuncios_diarios.yml deve existir.")

        with open(yml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        models = data.get("models", [])
        int_model = next((m for m in models if m.get("name") == "int_anuncios_diarios"), None)
        self.assertIsNotNone(int_model, "Modelo 'int_anuncios_diarios' deve estar definido em int_anuncios_diarios.yml")

        columns = {c["name"]: c for c in int_model.get("columns", [])}
        self.assertIn("surrogate_key", columns)
        self.assertIn("not_null", columns["surrogate_key"].get("tests", []))
        self.assertIn("property_fingerprint", columns)
        self.assertIn("not_null", columns["property_fingerprint"].get("tests", []))
        self.assertIn("preco", columns)
        self.assertIn("not_null", columns["preco"].get("tests", []))
        self.assertIn("data_coleta", columns)
        self.assertIn("not_null", columns["data_coleta"].get("tests", []))

    def test_silver_table_in_database(self):
        """Valida se a tabela silver.int_anuncios_diarios existe e possui dados válidos no Postgres."""
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
            # Verifica existência da tabela no schema silver
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'silver' AND table_name = 'int_anuncios_diarios';
            """)
            row = cur.fetchone()
            self.assertIsNotNone(row, "Tabela silver.int_anuncios_diarios deve existir no banco de dados.")

            # Valida regras de negócio nos dados
            cur.execute("""
                SELECT 
                    COUNT(*) AS total,
                    COUNT(DISTINCT surrogate_key) AS unique_keys,
                    MIN(preco) AS min_preco,
                    MAX(preco) AS max_preco,
                    MIN(banheiros) AS min_banheiros
                FROM silver.int_anuncios_diarios;
            """)
            stats = cur.fetchone()
            total, unique_keys, min_preco, max_preco, min_banheiros = stats

            self.assertGreater(total, 0, "A tabela silver.int_anuncios_diarios deve conter registros.")
            self.assertEqual(total, unique_keys, "Todos os surrogate_keys devem ser únicos por dia de coleta.")
            self.assertGreaterEqual(min_preco, 50000, "Preço mínimo deve respeitar o filtro de sanidade (>= 50k).")
            self.assertLessEqual(max_preco, 100000000, "Preço máximo deve respeitar o filtro de sanidade (<= 100M).")
            self.assertGreaterEqual(min_banheiros, 1, "Mínimo de banheiros saneado deve ser >= 1.")
        conn.close()


if __name__ == "__main__":
    unittest.main()
