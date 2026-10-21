"""
Loader Incremental do Data Lake (S3/MinIO) para o PostgreSQL (Data Warehouse).
Lê os lotes comprimidos em .jsonl.gz armazenados no bucket raw-imoveis,
garante a idempotência via tabela de controle de ingestão e insere os registros na tabela raw.landing_anuncios.
"""
import argparse
from datetime import datetime, timezone
import gzip
import io
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

import boto3
from dotenv import load_dotenv
from loguru import logger
import psycopg

# Carrega variáveis de ambiente
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class LakeToPostgresLoader:
    """
    Controlador de Ingestão Incremental: Data Lake -> PostgreSQL.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        s3_endpoint: Optional[str] = None,
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_region: str = "us-east-2",
        bucket_name: str = "raw-imoveis",
    ) -> None:
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL não configurada no ambiente ou .env")

        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME", "raw-imoveis")
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=s3_endpoint or os.getenv("AWS_ENDPOINT_URL_S3"),
            aws_access_key_id=aws_access_key or os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=aws_secret_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=aws_region or os.getenv("AWS_REGION", "us-east-2"),
        )

    def init_control_table(self) -> None:
        """Cria a tabela de auditoria e controle de arquivos ingeridos (raw.lake_ingestion_log)."""
        create_sql = """
        CREATE SCHEMA IF NOT EXISTS raw;

        CREATE TABLE IF NOT EXISTS raw.lake_ingestion_log (
            id BIGSERIAL PRIMARY KEY,
            file_key TEXT UNIQUE NOT NULL,
            source_portal VARCHAR(50) NOT NULL,
            batch_id VARCHAR(100) NOT NULL,
            records_count INTEGER NOT NULL,
            file_size_bytes BIGINT NOT NULL,
            ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_lake_ingest_portal ON raw.lake_ingestion_log(source_portal);
        CREATE INDEX IF NOT EXISTS idx_lake_ingest_batch ON raw.lake_ingestion_log(batch_id);
        """
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(create_sql)
            conn.commit()

    def get_already_ingested_files(self) -> Set[str]:
        """Recupera o conjunto de chaves S3 já carregadas anteriormente."""
        self.init_control_table()
        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT file_key FROM raw.lake_ingestion_log;")
                return {row[0] for row in cur.fetchall()}

    def list_s3_files(
        self,
        portal: Optional[str] = None,
        date_str: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lista os arquivos .jsonl.gz no S3 com base nos filtros informados.
        Suporta particionamento Hive: portal={portal}/year={YYYY}/month={MM}/day={DD}/...
        """
        prefix = ""
        if portal and portal.lower() not in ["all", "todos"]:
            canonical_portal = portal.lower().replace("-", "_")
            prefix = f"portal={canonical_portal}/"
            if date_str:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                prefix += f"year={dt.year:04d}/month={dt.month:02d}/day={dt.day:02d}/"

        logger.info(f"Listando arquivos no bucket '{self.bucket_name}' com prefixo: '{prefix}'...")
        paginator = self.s3_client.get_paginator("list_objects_v2")
        files = []

        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            for obj in page.get("Contents", []):
                key: str = obj["Key"]
                if key.endswith(".jsonl.gz"):
                    files.append({
                        "key": key,
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                    })

        logger.info(f"Encontrados {len(files)} arquivo(s) .jsonl.gz no Data Lake.")
        return files

    def load_file_content(self, file_key: str) -> Tuple[List[Dict[str, Any]], str, str]:
        """
        Baixa o arquivo do S3, descomprime o gzip e extrai a lista de registros JSON.
        Retorna (registros, source_portal, batch_id).
        """
        response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
        compressed_body = response["Body"].read()

        decompressed_text = gzip.decompress(compressed_body).decode("utf-8")
        records: List[Dict[str, Any]] = []

        source_portal = "desconhecido"
        batch_id = "desconhecido"

        for line in decompressed_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            records.append(item)
            if source_portal == "desconhecido" and item.get("source_portal"):
                source_portal = item["source_portal"]
            if batch_id == "desconhecido" and item.get("batch_id"):
                batch_id = item["batch_id"]

        return records, source_portal, batch_id

    def ingest_records(
        self,
        file_key: str,
        records: List[Dict[str, Any]],
        source_portal: str,
        batch_id: str,
        file_size: int,
    ) -> int:
        """
        Insere os registros na tabela raw.landing_anuncios e registra o log na raw.lake_ingestion_log.
        Executado de forma transacional e atômica.
        """
        if not records:
            return 0

        insert_record_sql = """
            INSERT INTO raw.landing_anuncios (
                source_portal,
                portal_listing_id,
                scraped_at,
                batch_id,
                url,
                payload
            ) VALUES (%s, %s, %s, %s, %s, %s);
        """

        insert_log_sql = """
            INSERT INTO raw.lake_ingestion_log (
                file_key,
                source_portal,
                batch_id,
                records_count,
                file_size_bytes
            ) VALUES (%s, %s, %s, %s, %s);
        """

        # Prepara os valores para inserção em lote
        rows = []
        for r in records:
            payload_json = json.dumps(r.get("payload", {}), ensure_ascii=False)
            rows.append((
                r.get("source_portal", source_portal),
                str(r.get("portal_listing_id", "")).strip(),
                r.get("scraped_at") or datetime.now(timezone.utc),
                r.get("batch_id", batch_id),
                r.get("url"),
                payload_json,
            ))

        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                # 1. Insere todos os anúncios
                cur.executemany(insert_record_sql, rows)
                # 2. Registra o log do arquivo na mesma transação
                cur.execute(
                    insert_log_sql,
                    (file_key, source_portal, batch_id, len(rows), file_size),
                )
            conn.commit()

        return len(rows)

    def run(
        self,
        portal: Optional[str] = None,
        date_str: Optional[str] = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> int:
        """
        Executa a rotina completa de ingestão incremental.
        Retorna o total de registros carregados.
        """
        logger.info("=" * 70)
        logger.info("INICIANDO LOADER INCREMENTAL: DATA LAKE -> POSTGRES (RAW)")
        logger.info(f"Bucket: {self.bucket_name} | Forçar recarga: {force} | Dry-run: {dry_run}")
        logger.info("=" * 70)

        ingested_keys: Set[str] = set() if force else self.get_already_ingested_files()
        all_files = self.list_s3_files(portal=portal, date_str=date_str)

        files_to_process = [f for f in all_files if f["key"] not in ingested_keys]
        already_processed_count = len(all_files) - len(files_to_process)

        logger.info(f"Total de arquivos no lake: {len(all_files)}")
        logger.info(f"Arquivos já ingeridos anteriormente: {already_processed_count}")
        logger.info(f"Arquivos pendentes de carga: {len(files_to_process)}")

        if not files_to_process:
            logger.info("Nenhum arquivo novo pendente para carga. Lakehouse atualizado! ✅")
            return 0

        total_records_loaded = 0

        for idx, file_info in enumerate(files_to_process, start=1):
            key = file_info["key"]
            size = file_info["size"]

            logger.info(f"[{idx}/{len(files_to_process)}] Baixando e descompactando: {key} ({size:,} bytes)...")

            records, source_portal, batch_id = self.load_file_content(key)
            logger.info(f"  -> {len(records)} registros extraídos | Portal: {source_portal} | Batch: {batch_id}")

            if dry_run:
                logger.info("  [Dry-run] Simulação ativada. Inserção ignorada.")
                total_records_loaded += len(records)
                continue

            loaded = self.ingest_records(
                file_key=key,
                records=records,
                source_portal=source_portal,
                batch_id=batch_id,
                file_size=size,
            )
            total_records_loaded += loaded
            logger.info(f"  -> {loaded} registros inseridos com sucesso na tabela raw.landing_anuncios! ✅")

        logger.info("=" * 70)
        logger.info("CARGA CONCLUÍDA COM SUCESSO!")
        logger.info(f"Arquivos processados: {len(files_to_process)}")
        logger.info(f"Total de anúncios carregados na landing zone: {total_records_loaded}")
        logger.info("=" * 70)

        return total_records_loaded


def main():
    parser = argparse.ArgumentParser(
        description="Loader incremental dos lotes brutos (.jsonl.gz) do Data Lake para o PostgreSQL (Raw Landing)."
    )
    parser.add_argument("--portal", type=str, default=None, help="Filtrar por portal (ex: quinto_andar, chaves_na_mao, all)")
    parser.add_argument("--date", type=str, default=None, help="Filtrar por data no formato YYYY-MM-DD")
    parser.add_argument("--force", action="store_true", help="Forçar recarga de arquivos mesmo se já constarem no log")
    parser.add_argument("--dry-run", action="store_true", help="Simula a execução sem gravar no banco de dados")

    args = parser.parse_args()

    try:
        loader = LakeToPostgresLoader()
        loader.run(portal=args.portal, date_str=args.date, force=args.force, dry_run=args.dry_run)
        sys.exit(0)
    except Exception as err:
        logger.error(f"Falha na execução do Loader: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
