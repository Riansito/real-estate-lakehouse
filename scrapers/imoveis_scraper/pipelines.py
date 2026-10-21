"""
Pipelines do Scrapy para processamento e armazenamento de anúncios coletados.
Implementa o MinIOStoragePipeline, responsável por particionar, comprimir em .jsonl.gz
e fazer upload dos lotes brutos diretamente no Data Lake compatível com AWS S3 / MinIO.
"""
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from itemadapter import ItemAdapter
from loguru import logger
import scrapy


class MinIOStoragePipeline:
    """
    Pipeline de armazenamento no Data Lake S3/MinIO.
    
    Responsabilidades:
    1. Agrupar os itens coletados pelo identificador do portal de origem (source_portal).
    2. Serializar os envelopes no formato JSONL (JSON Lines).
    3. Comprimir o payload utilizando gzip (.jsonl.gz) para economia de I/O e armazenamento.
    4. Enviar para o Data Lake estruturado na convenção de particionamento Hive:
       s3://{bucket}/portal={portal}/year={YYYY}/month={MM}/day={DD}/{portal}_{timestamp}_{batch_id}.jsonl.gz
    5. Registrar metadados S3 (item_count, batch_id, portal) no objeto.
    """

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        region_name: str = "us-east-2",
        bucket_name: str = "raw-imoveis",
        enabled: bool = True,
        fallback_local_dir: Optional[str] = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region_name = region_name
        self.bucket_name = bucket_name
        self.enabled = enabled
        self.fallback_local_dir = fallback_local_dir

        self.s3_client = None
        self.items_by_portal: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.uploaded_objects: List[Dict[str, Any]] = []

    @classmethod
    def from_crawler(cls, crawler: Any):
        settings = crawler.settings
        return cls(
            endpoint_url=settings.get("AWS_ENDPOINT_URL"),
            access_key=settings.get("AWS_ACCESS_KEY_ID"),
            secret_key=settings.get("AWS_SECRET_ACCESS_KEY"),
            region_name=settings.get("AWS_REGION_NAME", "us-east-2"),
            bucket_name=settings.get("S3_BUCKET_NAME", "raw-imoveis"),
            enabled=settings.getbool("MINIO_PIPELINE_ENABLED", True),
            fallback_local_dir=settings.get("FALLBACK_LOCAL_DIR", None),
        )

    def open_spider(self, spider: scrapy.Spider) -> None:
        """Inicializa a conexão com o Data Lake S3 / MinIO e valida o bucket."""
        if not self.enabled:
            logger.info("MinIOStoragePipeline está desativado por configuração.")
            return

        logger.info(
            f"Inicializando MinIOStoragePipeline | Bucket: {self.bucket_name} | "
            f"Endpoint: {self.endpoint_url or 'AWS S3 Padrão'}"
        )

        try:
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region_name,
            )

            # Valida ou cria o bucket se necessário
            try:
                response = self.s3_client.list_buckets()
                existing_buckets = [b["Name"] for b in response.get("Buckets", [])]
                if self.bucket_name not in existing_buckets:
                    logger.info(f"Bucket '{self.bucket_name}' não encontrado. Criando bucket...")
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Bucket '{self.bucket_name}' criado com sucesso.")
            except Exception as bucket_err:
                logger.warning(
                    f"Aviso ao listar/criar bucket (prosseguindo assumindo que bucket já existe): {bucket_err}"
                )

        except Exception as err:
            logger.error(f"Falha ao inicializar cliente S3/MinIO: {err}")
            self.s3_client = None

    def process_item(self, item: Any, spider: scrapy.Spider) -> Any:
        """
        Recebe cada anúncio coletado pelo spider e acumula no buffer agrupado por portal.
        """
        if not self.enabled:
            return item

        item_dict = ItemAdapter(item).asdict()
        portal = item_dict.get("source_portal") or getattr(spider, "portal_arg", "unknown_portal")
        self.items_by_portal[portal].append(item_dict)
        return item

    def close_spider(self, spider: scrapy.Spider) -> None:
        """
        Ao finalizar o spider, consolida os buffers por portal em arquivos .jsonl.gz
        e realiza o upload particionado no Data Lake.
        """
        if not self.enabled:
            return

        total_buffered = sum(len(items) for items in self.items_by_portal.values())
        if total_buffered == 0:
            logger.info("Nenhum item coletado para envio ao Data Lake.")
            return

        logger.info(
            f"Consolidando {total_buffered} itens em {len(self.items_by_portal)} portal(is) "
            f"para envio ao Data Lake..."
        )

        # Determina timestamp e batch_id para o lote
        batch_id = getattr(spider, "batch_id", "batch_desconhecido")
        scraped_at_str = getattr(spider, "scraped_at", None)

        dt: datetime
        if scraped_at_str:
            try:
                dt = datetime.fromisoformat(scraped_at_str.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)

        year_str = f"{dt.year:04d}"
        month_str = f"{dt.month:02d}"
        day_str = f"{dt.day:02d}"
        timestamp_str = dt.strftime("%Y%m%d_%H%M%S")

        for portal_name, items in self.items_by_portal.items():
            if not items:
                continue

            self._upload_portal_batch(
                portal_name=portal_name,
                items=items,
                year=year_str,
                month=month_str,
                day=day_str,
                timestamp_str=timestamp_str,
                batch_id=batch_id,
                scraped_at=scraped_at_str or dt.isoformat(),
            )

    def _upload_portal_batch(
        self,
        portal_name: str,
        items: List[Dict[str, Any]],
        year: str,
        month: str,
        day: str,
        timestamp_str: str,
        batch_id: str,
        scraped_at: str,
    ) -> None:
        """
        Serializa, comprime e envia um lote específico de um portal para o S3.
        """
        # Monta chave S3 particionada:
        # portal=quintoandar/year=2026/month=10/day=21/quinto_andar_20261021_153000_uuid.jsonl.gz
        partition_prefix = f"portal={portal_name}/year={year}/month={month}/day={day}"
        file_name = f"{portal_name}_{timestamp_str}_{batch_id}.jsonl.gz"
        s3_key = f"{partition_prefix}/{file_name}"

        # 1. Serialização em JSON Lines (JSONL)
        lines = [json.dumps(it, ensure_ascii=False) for it in items]
        jsonl_content = "\n".join(lines) + "\n"
        uncompressed_bytes = jsonl_content.encode("utf-8")
        uncompressed_size = len(uncompressed_bytes)

        # 2. Compressão em Gzip
        compressed_bytes = gzip.compress(uncompressed_bytes, compresslevel=9)
        compressed_size = len(compressed_bytes)
        compression_ratio = (
            (1.0 - (compressed_size / uncompressed_size)) * 100 if uncompressed_size > 0 else 0
        )

        logger.info(
            f"[{portal_name}] Compactação concluída: {len(items)} anúncios | "
            f"Original: {uncompressed_size:,} bytes | Gzip: {compressed_size:,} bytes "
            f"(-{compression_ratio:.1f}%)"
        )

        # 3. Upload para o S3 / MinIO
        uploaded_successfully = False
        if self.s3_client:
            try:
                logger.info(f"[{portal_name}] Enviando para s3://{self.bucket_name}/{s3_key} ...")
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=compressed_bytes,
                    ContentType="application/gzip",
                    Metadata={
                        "portal": portal_name,
                        "batch_id": batch_id,
                        "item_count": str(len(items)),
                        "scraped_at": scraped_at,
                    },
                )
                logger.info(f"[{portal_name}] Upload para Data Lake concluído com sucesso! ✅")
                self.uploaded_objects.append(
                    {
                        "portal": portal_name,
                        "s3_key": s3_key,
                        "bucket": self.bucket_name,
                        "item_count": len(items),
                        "size_bytes": compressed_size,
                    }
                )
                uploaded_successfully = True
            except Exception as upload_err:
                logger.error(f"[{portal_name}] Erro no upload para S3 (s3://{self.bucket_name}/{s3_key}): {upload_err}")

        # 4. Fallback Local de Segurança (caso o S3 falhe ou esteja configurado diretório local)
        if not uploaded_successfully or self.fallback_local_dir:
            self._save_local_backup(s3_key=s3_key, data=compressed_bytes)

    def _save_local_backup(self, s3_key: str, data: bytes) -> None:
        """Salva uma cópia local caso configurado ou em caso de contingência."""
        target_dir = Path(self.fallback_local_dir or "data/lake_raw_backup")
        local_file = target_dir / s3_key
        try:
            local_file.parent.mkdir(parents=True, exist_ok=True)
            local_file.write_bytes(data)
            logger.info(f"Backup local salvo com segurança em: {local_file}")
        except Exception as err:
            logger.error(f"Falha ao salvar backup local em {local_file}: {err}")
