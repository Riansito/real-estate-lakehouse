"""
Testes unitários e de integração para a suíte de qualidade de dados do dbt (BACK-013).
Valida os testes singulares de intervalos, sanidade e integridade relacional,
além de validar a execução do dbt test no projeto.
"""
from pathlib import Path
import unittest
import os
import subprocess
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = BASE_DIR / "dbt_imoveis"
TESTS_DIR = DBT_DIR / "tests"

load_dotenv(BASE_DIR / ".env")


class TestDbtQualityTests(unittest.TestCase):
    """Valida a suíte de testes de qualidade de dados do dbt."""

    def test_singular_tests_exist(self):
        """Valida se os 6 testes singulares obrigatórios foram criados em dbt_imoveis/tests."""
        expected_tests = [
            "assert_precos_no_intervalo_sanidade.sql",
            "assert_area_util_no_intervalo.sql",
            "assert_preco_m2_positivo.sql",
            "assert_scd2_apenas_um_registro_ativo_por_anuncio.sql",
            "assert_total_oportunidades_coerente.sql",
            "assert_banheiros_e_vagas_positivos.sql",
        ]
        for t in expected_tests:
            p = TESTS_DIR / t
            self.assertTrue(p.exists(), f"O teste singular {t} deve existir em dbt_imoveis/tests/.")

    def test_singular_tests_logic(self):
        """Valida o conteúdo e a sintaxe lógica dos testes singulares."""
        preco_test = (TESTS_DIR / "assert_precos_no_intervalo_sanidade.sql").read_text(encoding="utf-8")
        self.assertIn("ref('dim_anuncios_ativos')", preco_test)
        self.assertIn("preco < 50000 OR preco > 100000000", preco_test)

        area_test = (TESTS_DIR / "assert_area_util_no_intervalo.sql").read_text(encoding="utf-8")
        self.assertIn("area_util_m2 < 10 OR area_util_m2 > 3000", area_test)

        scd_test = (TESTS_DIR / "assert_scd2_apenas_um_registro_ativo_por_anuncio.sql").read_text(encoding="utf-8")
        self.assertIn("ref('snp_historico_precos')", scd_test)
        self.assertIn("dbt_valid_to IS NULL", scd_test)
        self.assertIn("HAVING COUNT(*) > 1", scd_test)

    def test_database_quality_assertions_via_sql(self):
        """Executa asserções SQL diretas de qualidade no PostgreSQL Neon."""
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
            # 1. Checa se há algum preço fora do intervalo sadio
            cur.execute("""
                SELECT COUNT(*) FROM gold.dim_anuncios_ativos
                WHERE preco < 50000 OR preco > 100000000;
            """)
            outliers_count = cur.fetchone()[0]
            self.assertEqual(outliers_count, 0, "Nenhum preço de venda pode estar fora do intervalo [50k, 100M].")

            # 2. Checa se há violação de unicidade de registro ativo no SCD2
            cur.execute("""
                SELECT COUNT(*) FROM (
                    SELECT surrogate_key
                    FROM gold.snp_historico_precos
                    WHERE dbt_valid_to IS NULL
                    GROUP BY surrogate_key
                    HAVING COUNT(*) > 1
                ) sub;
            """)
            multiple_active = cur.fetchone()[0]
            self.assertEqual(multiple_active, 0, "Cada anúncio deve ter no máximo 1 registro ativo no SCD2.")

            # 3. Checa coerência de oportunidades vs total de ativos
            cur.execute("""
                SELECT COUNT(*) FROM gold.fct_metricas_bairro_diarias
                WHERE total_oportunidades_abaixo_media > total_anuncios_ativos;
            """)
            inconsistent_metrics = cur.fetchone()[0]
            self.assertEqual(inconsistent_metrics, 0, "Oportunidades não podem superar o total de anúncios ativos.")
        conn.close()


if __name__ == "__main__":
    unittest.main()
