"""
Testes unitários e de integração para o snapshot dbt snp_historico_precos.
Valida arquivos de especificação (snapshot SQL e schema YAML)
e integridade da tabela histórica SCD Tipo 2 gerada no banco de dados.
"""
from pathlib import Path
import unittest
import os
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DBT_DIR = BASE_DIR / "dbt_imoveis"
SNAPSHOTS_DIR = DBT_DIR / "snapshots"

load_dotenv(BASE_DIR / ".env")


class TestSnpHistoricoPrecos(unittest.TestCase):
    """Valida especificações e comportamento do snapshot snp_historico_precos."""

    def test_snapshot_sql_exists_and_syntax(self):
        """Valida existência do arquivo de snapshot e configurações do SCD Tipo 2."""
        sql_file = SNAPSHOTS_DIR / "snp_historico_precos.sql"
        self.assertTrue(sql_file.exists(), "snp_historico_precos.sql deve existir.")

        content = sql_file.read_text(encoding="utf-8")
        self.assertIn("{% snapshot snp_historico_precos %}", content)
        self.assertIn("target_schema='gold'", content)
        self.assertIn("unique_key='surrogate_key'", content)
        self.assertIn("strategy='check'", content)
        self.assertIn("check_cols=['preco', 'valor_condominio', 'valor_iptu']", content)
        self.assertIn("ref('int_anuncios_diarios')", content)
        self.assertIn("{% endsnapshot %}", content)

    def test_snapshot_yml_exists_and_schema_tests(self):
        """Valida documentação e testes de schema do snapshot em snp_historico_precos.yml."""
        yml_file = SNAPSHOTS_DIR / "snp_historico_precos.yml"
        self.assertTrue(yml_file.exists(), "snp_historico_precos.yml deve existir.")

        with open(yml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        snapshots = data.get("snapshots", [])
        snp_model = next((s for s in snapshots if s.get("name") == "snp_historico_precos"), None)
        self.assertIsNotNone(snp_model, "Snapshot 'snp_historico_precos' deve estar declarado no YAML.")

        columns = {c["name"]: c for c in snp_model.get("columns", [])}
        self.assertIn("surrogate_key", columns)
        self.assertIn("not_null", columns["surrogate_key"].get("tests", []))
        self.assertIn("dbt_scd_id", columns)
        self.assertIn("unique", columns["dbt_scd_id"].get("tests", []))
        self.assertIn("not_null", columns["dbt_scd_id"].get("tests", []))
        self.assertIn("dbt_valid_from", columns)
        self.assertIn("not_null", columns["dbt_valid_from"].get("tests", []))

    def test_gold_snapshot_in_database(self):
        """Valida se a tabela gold.snp_historico_precos existe e possui colunas nativas do SCD2."""
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
            # Checa existência da tabela no schema gold
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'gold' AND table_name = 'snp_historico_precos';
            """)
            row = cur.fetchone()
            self.assertIsNotNone(row, "Tabela gold.snp_historico_precos deve existir no banco de dados.")

            # Checa colunas SCD2 nativas do dbt
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'gold' AND table_name = 'snp_historico_precos';
            """)
            existing_cols = {r[0] for r in cur.fetchall()}
            for col in ["dbt_scd_id", "dbt_updated_at", "dbt_valid_from", "dbt_valid_to", "surrogate_key", "preco"]:
                self.assertIn(col, existing_cols, f"Coluna {col} deve estar presente em gold.snp_historico_precos.")

            # Valida contagem de registros ativos (dbt_valid_to IS NULL)
            cur.execute("SELECT COUNT(*) FROM gold.snp_historico_precos WHERE dbt_valid_to IS NULL;")
            active_count = cur.fetchone()[0]
            self.assertGreater(active_count, 0, "Deve haver registros vigentes (dbt_valid_to IS NULL).")
        conn.close()


if __name__ == "__main__":
    unittest.main()
