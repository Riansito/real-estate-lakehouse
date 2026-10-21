"""
Testes unitários da DAG diária do Apache Airflow (dag_imoveis_pipeline.py).
Valida estrutura, metadados, parâmetros, dependências downstream/upstream e comandos bash.
"""
import ast
import os
from pathlib import Path
import unittest

from dags.dag_imoveis_pipeline import (
    dag,
    start_pipeline,
    scrape_real_estate_portals,
    ingest_lake_to_postgres,
    dbt_run_transformations,
    dbt_snapshot_scd2,
    dbt_test_quality_gates,
    end_pipeline,
)


class TestAirflowDAGPipeline(unittest.TestCase):
    """Testes de conformidade e integridade da DAG do Real Estate Lakehouse."""

    def test_dag_metadata(self):
        """Valida metadados fundamentais da DAG (ID, agendamento, catchup, tags)."""
        self.assertEqual(dag.dag_id, "dag_imoveis_lakehouse_pipeline")
        self.assertFalse(dag.catchup)
        self.assertEqual(dag.schedule_interval, "0 6 * * *")
        self.assertIn("lakehouse", dag.tags)
        self.assertIn("scrapy", dag.tags)
        self.assertIn("dbt", dag.tags)

    def test_dag_default_args(self):
        """Valida que default_args possui retries, retry_delay e políticas seguras."""
        self.assertEqual(dag.default_args.get("owner"), "real-estate-team")
        self.assertFalse(dag.default_args.get("depends_on_past"))
        self.assertFalse(dag.default_args.get("email_on_failure"))
        self.assertEqual(dag.default_args.get("retries"), 2)
        self.assertIsNotNone(dag.default_args.get("retry_delay"))
        self.assertIsNotNone(dag.default_args.get("execution_timeout"))

    def test_tasks_existence_and_ids(self):
        """Valida que todas as 7 tarefas requeridas existem com IDs padronizados."""
        expected_ids = {
            "start_pipeline",
            "scrape_real_estate_portals",
            "ingest_lake_to_postgres",
            "dbt_run_transformations",
            "dbt_snapshot_scd2",
            "dbt_test_quality_gates",
            "end_pipeline",
        }
        actual_ids = {
            start_pipeline.task_id,
            scrape_real_estate_portals.task_id,
            ingest_lake_to_postgres.task_id,
            dbt_run_transformations.task_id,
            dbt_snapshot_scd2.task_id,
            dbt_test_quality_gates.task_id,
            end_pipeline.task_id,
        }
        self.assertEqual(expected_ids, actual_ids)

    def test_task_bash_commands(self):
        """Valida se os comandos bash das tarefas contêm as chamadas corretas."""
        # Scrapy
        self.assertIn("scrapy crawl imoveis", scrape_real_estate_portals.bash_command)
        self.assertIn("-a portal=", scrape_real_estate_portals.bash_command)
        self.assertIn("-a batch_id=", scrape_real_estate_portals.bash_command)

        # Loader
        self.assertIn("lake_to_postgres_loader.py", ingest_lake_to_postgres.bash_command)
        self.assertIn("--portal", ingest_lake_to_postgres.bash_command)

        # dbt Run
        self.assertIn("dbt run", dbt_run_transformations.bash_command)
        self.assertIn("--profiles-dir", dbt_run_transformations.bash_command)

        # dbt Snapshot (SCD2)
        self.assertIn("dbt snapshot", dbt_snapshot_scd2.bash_command)

        # dbt Test
        self.assertIn("dbt test", dbt_test_quality_gates.bash_command)

    def test_pipeline_dependency_chain(self):
        """Valida que o grafo de dependências downstream é estrito e linear."""
        # start_pipeline -> scrape
        self.assertIn(scrape_real_estate_portals, start_pipeline.downstream_list)
        # scrape -> ingestao
        self.assertIn(ingest_lake_to_postgres, scrape_real_estate_portals.downstream_list)
        # ingestao -> dbt_run
        self.assertIn(dbt_run_transformations, ingest_lake_to_postgres.downstream_list)
        # dbt_run -> dbt_snapshot
        self.assertIn(dbt_snapshot_scd2, dbt_run_transformations.downstream_list)
        # dbt_snapshot -> dbt_test
        self.assertIn(dbt_test_quality_gates, dbt_snapshot_scd2.downstream_list)
        # dbt_test -> end_pipeline
        self.assertIn(end_pipeline, dbt_test_quality_gates.downstream_list)

    def test_dag_file_ast_validity(self):
        """Valida a árvore sintática (AST) do arquivo da DAG sem erros."""
        dag_file = Path(__file__).resolve().parent.parent / "dags" / "dag_imoveis_pipeline.py"
        self.assertTrue(dag_file.exists())

        with open(dag_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        self.assertIsInstance(tree, ast.Module)


if __name__ == "__main__":
    unittest.main()
