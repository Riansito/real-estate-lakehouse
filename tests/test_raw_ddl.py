"""
Testes unitários e de integração para o schema raw e tabela landing_anuncios.
Valida integridade do DDL, existência das colunas, índices e operações nativas de JSONB.
"""
import json
import os
from pathlib import Path
import unittest
from dotenv import load_dotenv
import psycopg

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class TestRawLandingAnuncios(unittest.TestCase):
    """Valida a camada de pouso (Raw Landing) no PostgreSQL."""

    @classmethod
    def setUpClass(cls):
        cls.db_url = os.getenv("DATABASE_URL")
        cls.ddl_file = BASE_DIR / "sql" / "ddl" / "01_create_raw_landing_anuncios.sql"

    def test_ddl_file_exists(self):
        """Garante a existência do script DDL versionado."""
        self.assertTrue(self.ddl_file.exists(), "O arquivo DDL sql/ddl/01_create_raw_landing_anuncios.sql deve existir.")
        content = self.ddl_file.read_text(encoding="utf-8")
        self.assertIn("CREATE SCHEMA IF NOT EXISTS raw", content)
        self.assertIn("CREATE TABLE IF NOT EXISTS raw.landing_anuncios", content)
        self.assertIn("payload JSONB NOT NULL", content)

    def test_table_columns_and_types(self):
        """Verifica se a tabela landing_anuncios existe no banco com as colunas e tipos corretos."""
        if not self.db_url:
            self.skipTest("DATABASE_URL não configurada.")

        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'raw' AND table_name = 'landing_anuncios'
                    ORDER BY ordinal_position;
                """)
                columns = {row[0]: {"type": row[1], "nullable": row[2]} for row in cur.fetchall()}

        expected_columns = {
            "id": "bigint",
            "source_portal": "character varying",
            "portal_listing_id": "character varying",
            "scraped_at": "timestamp with time zone",
            "batch_id": "character varying",
            "url": "text",
            "payload": "jsonb",
            "created_at": "timestamp with time zone",
        }

        for col, expected_type in expected_columns.items():
            self.assertIn(col, columns, f"Coluna '{col}' ausente na tabela raw.landing_anuncios.")
            self.assertEqual(
                columns[col]["type"],
                expected_type,
                f"Tipo da coluna '{col}' ({columns[col]['type']}) difere do esperado ({expected_type}).",
            )

    def test_jsonb_insert_and_query(self):
        """Valida inserção e consulta de campos em JSONB na tabela landing_anuncios."""
        if not self.db_url:
            self.skipTest("DATABASE_URL não configurada.")

        test_payload = {
            "title": "Apartamento Teste Moema",
            "price": 750000.0,
            "condo_fee": 800.0,
            "address": {
                "neighborhood": "Moema",
                "city": "São Paulo",
            },
        }

        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                # Insere registro de teste
                cur.execute("""
                    INSERT INTO raw.landing_anuncios (
                        source_portal, portal_listing_id, scraped_at, batch_id, url, payload
                    ) VALUES (
                        %s, %s, NOW(), %s, %s, %s
                    ) RETURNING id;
                """, (
                    "test_portal",
                    "test-id-9999",
                    "test-batch-raw-test",
                    "https://test.com/imovel/9999",
                    json.dumps(test_payload),
                ))
                inserted_id = cur.fetchone()[0]

                # Consulta utilizando operadores nativos de JSONB do PostgreSQL (->> e ->)
                cur.execute("""
                    SELECT 
                        source_portal,
                        payload->>'title' AS titulo,
                        (payload->>'price')::NUMERIC AS preco,
                        payload->'address'->>'neighborhood' AS bairro
                    FROM raw.landing_anuncios
                    WHERE id = %s;
                """, (inserted_id,))
                row = cur.fetchone()

                self.assertEqual(row[0], "test_portal")
                self.assertEqual(row[1], "Apartamento Teste Moema")
                self.assertEqual(float(row[2]), 750000.0)
                self.assertEqual(row[3], "Moema")

                # Limpa o registro de teste
                cur.execute("DELETE FROM raw.landing_anuncios WHERE id = %s;", (inserted_id,))
            conn.commit()


if __name__ == "__main__":
    unittest.main()
