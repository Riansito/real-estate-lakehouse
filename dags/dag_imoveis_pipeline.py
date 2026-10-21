"""
DAG Diária do Real Estate Lakehouse: Orquestração Ponta a Ponta.
Fluxo ELT: Scrapy (Coleta) -> MinIO/S3 (Raw Lake) -> Loader (PostgreSQL Landing) -> dbt (Staging, Silver, Gold, SCD2) -> dbt test (Qualidade).
"""
from datetime import datetime, timedelta
import os
from pathlib import Path
import sys

# Compatibilidade e resiliência: suporta Airflow 2.x nativo e mock gracioso para validação estática
try:
    from airflow import DAG
    from airflow.operators.bash import BashOperator
    try:
        from airflow.operators.empty import EmptyOperator
    except ImportError:
        from airflow.operators.dummy import DummyOperator as EmptyOperator
except ImportError:
    class _MockTask:
        def __init__(self, task_id: str, **kwargs):
            self.task_id = task_id
            self.kwargs = kwargs
            self.bash_command = kwargs.get("bash_command", "")
            self.downstream_list = []
            self.upstream_list = []

        def __rshift__(self, other):
            if isinstance(other, (list, tuple)):
                for o in other:
                    self.__rshift__(o)
                return other
            self.downstream_list.append(other)
            other.upstream_list.append(self)
            return other

        def __lshift__(self, other):
            return other.__rshift__(self)

    class DAG:
        def __init__(self, dag_id: str, **kwargs):
            self.dag_id = dag_id
            self.kwargs = kwargs
            self.tasks = []
            self.default_args = kwargs.get("default_args", {})
            self.schedule_interval = kwargs.get("schedule") or kwargs.get("schedule_interval")
            self.catchup = kwargs.get("catchup", True)
            self.tags = kwargs.get("tags", [])
            self.description = kwargs.get("description", "")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def add_task(self, task):
            self.tasks.append(task)

    class EmptyOperator(_MockTask):
        pass

    class BashOperator(_MockTask):
        pass


# Configurações de Caminhos e Ambiente
# No container do Airflow, o repositório é montado em /opt/airflow/project
PROJECT_DIR = os.getenv("AIRFLOW_PROJECT_DIR", "/opt/airflow/project")
SCRAPERS_DIR = os.path.join(PROJECT_DIR, "scrapers")
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "scripts")
DBT_DIR = os.path.join(PROJECT_DIR, "dbt_imoveis")

# Parâmetros padrão de scraping
DEFAULT_PORTALS = os.getenv("AIRFLOW_SCRAPING_PORTALS", "all")
DEFAULT_CITY = os.getenv("AIRFLOW_SCRAPING_CITY", "sao-paulo")
DEFAULT_STATE = os.getenv("AIRFLOW_SCRAPING_STATE", "sp")
DEFAULT_MAX_PAGES = os.getenv("AIRFLOW_SCRAPING_MAX_PAGES", "10")

# Argumentos Padrão da DAG
default_args = {
    "owner": "real-estate-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "execution_timeout": timedelta(hours=2),
}

# Definição da DAG
with DAG(
    dag_id="dag_imoveis_lakehouse_pipeline",
    default_args=default_args,
    description="Pipeline diário do Real Estate Lakehouse: Scrapy -> Data Lake S3 -> Postgres Landing -> dbt (Staging, Silver, Gold, SCD2) -> Quality Gates",
    schedule="0 6 * * *",  # Executa diariamente às 06:00 UTC (03:00 Horário de Brasília)
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "real-estate", "scrapy", "dbt", "gold", "scd2"],
) as dag:

    # 1. Marco Inicial do Pipeline
    start_pipeline = EmptyOperator(
        task_id="start_pipeline",
    )

    # 2. Coleta Scrapy com envio ao Data Lake (MinIO/S3)
    # Executa o spider adaptativo salvando lotes brutos particionados em .jsonl.gz
    scrape_real_estate_portals = BashOperator(
        task_id="scrape_real_estate_portals",
        bash_command=(
            f"cd {SCRAPERS_DIR} && "
            f"scrapy crawl imoveis "
            f"-a portal={DEFAULT_PORTALS} "
            f"-a city={DEFAULT_CITY} "
            f"-a state={DEFAULT_STATE} "
            f"-a business_type=venda "
            f"-a max_pages={DEFAULT_MAX_PAGES} "
            f"-a batch_id={{{{ ds_nodash }}}}_{{{{ ts_nodash }}}}"
        ),
        env={
            "PYTHONPATH": f"{PROJECT_DIR}:{SCRAPERS_DIR}",
        },
        append_env=True,
    )

    # 3. Ingestão Incremental do Data Lake para o PostgreSQL (Raw Landing)
    # Lê os novos arquivos do S3, verifica auditoria e insere em raw.landing_anuncios
    ingest_lake_to_postgres = BashOperator(
        task_id="ingest_lake_to_postgres",
        bash_command=(
            f"python {os.path.join(SCRIPTS_DIR, 'lake_to_postgres_loader.py')} "
            f"--portal {DEFAULT_PORTALS}"
        ),
        env={
            "PYTHONPATH": PROJECT_DIR,
        },
        append_env=True,
    )

    # 4. Transformações dbt (Staging, Intermediate/Silver e Marts/Gold)
    # Executa stg_anuncios, int_anuncios_diarios, dim_anuncios_ativos e fct_metricas_bairro_diarias
    dbt_run_transformations = BashOperator(
        task_id="dbt_run_transformations",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt run --profiles-dir . --project-dir ."
        ),
        env={
            "PYTHONPATH": PROJECT_DIR,
        },
        append_env=True,
    )

    # 5. Snapshots dbt (Rastreamento Histórico de Preços - SCD Tipo 2)
    # Atualiza snp_historico_precos capturando variações de valores de anúncios
    dbt_snapshot_scd2 = BashOperator(
        task_id="dbt_snapshot_scd2",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt snapshot --profiles-dir . --project-dir ."
        ),
        env={
            "PYTHONPATH": PROJECT_DIR,
        },
        append_env=True,
    )

    # 6. Quality Gates com dbt test
    # Valida integridade, unicidade, não-nulos e intervalos antes do fechamento
    dbt_test_quality_gates = BashOperator(
        task_id="dbt_test_quality_gates",
        bash_command=(
            f"cd {DBT_DIR} && "
            f"dbt test --profiles-dir . --project-dir ."
        ),
        env={
            "PYTHONPATH": PROJECT_DIR,
        },
        append_env=True,
    )

    # 7. Marco Final do Pipeline
    end_pipeline = EmptyOperator(
        task_id="end_pipeline",
    )

    # Definição Linear e Idempotente do Fluxo
    (
        start_pipeline
        >> scrape_real_estate_portals
        >> ingest_lake_to_postgres
        >> dbt_run_transformations
        >> dbt_snapshot_scd2
        >> dbt_test_quality_gates
        >> end_pipeline
    )
