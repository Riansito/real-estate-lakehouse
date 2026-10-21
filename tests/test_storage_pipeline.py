"""
Testes unitários para o MinIOStoragePipeline.
Valida o agrupamento por portal, a compressão .jsonl.gz, a convenção de particionamento Hive
e o upload seguro de metadados no Data Lake.
"""
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

# Adiciona scrapers ao path
scrapers_dir = Path(__file__).resolve().parent.parent / "scrapers"
if str(scrapers_dir) not in sys.path:
    sys.path.insert(0, str(scrapers_dir))

from scrapy.spiders import Spider
from imoveis_scraper.items import RawPropertyItem
from imoveis_scraper.pipelines import MinIOStoragePipeline


class TestMinIOStoragePipeline(unittest.TestCase):
    """Suíte de testes para a camada de armazenamento no Data Lake."""

    def setUp(self):
        self.pipeline = MinIOStoragePipeline(
            endpoint_url="http://localhost:9000",
            access_key="test_access",
            secret_key="test_secret",
            region_name="us-east-2",
            bucket_name="raw-imoveis",
            enabled=True,
        )
        self.spider = Spider("test_spider")
        self.spider.batch_id = "test-batch-uuid-1234"
        self.spider.scraped_at = "2026-10-21T15:30:00+00:00"

    def test_process_item_buffers_by_portal(self):
        """Valida se os itens são devidamente agrupados por portal."""
        item1 = RawPropertyItem(
            source_portal="quinto_andar",
            portal_listing_id="101",
            scraped_at=self.spider.scraped_at,
            batch_id=self.spider.batch_id,
            url="https://quintoandar.com.br/imovel/101",
            payload={"price": 350000},
        )
        item2 = RawPropertyItem(
            source_portal="chaves_na_mao",
            portal_listing_id="202",
            scraped_at=self.spider.scraped_at,
            batch_id=self.spider.batch_id,
            url="https://chavesnamao.com.br/imovel/202",
            payload={"price": 420000},
        )

        self.pipeline.process_item(item1, self.spider)
        self.pipeline.process_item(item2, self.spider)

        self.assertIn("quinto_andar", self.pipeline.items_by_portal)
        self.assertIn("chaves_na_mao", self.pipeline.items_by_portal)
        self.assertEqual(len(self.pipeline.items_by_portal["quinto_andar"]), 1)
        self.assertEqual(len(self.pipeline.items_by_portal["chaves_na_mao"]), 1)

    @patch("boto3.client")
    def test_upload_batch_compression_and_hive_partition(self, mock_boto):
        """Valida compressão gzip, nome de arquivo particionado e chamada S3."""
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        self.pipeline.s3_client = mock_s3

        item = {
            "source_portal": "quinto_andar",
            "portal_listing_id": "894101874",
            "scraped_at": "2026-10-21T15:30:00+00:00",
            "batch_id": "test-batch-uuid-1234",
            "url": "https://quintoandar.com.br/imovel/894101874",
            "payload": {"title": "Apartamento Moema", "price": 500000.0},
        }
        self.pipeline.items_by_portal["quinto_andar"].append(item)

        self.pipeline.close_spider(self.spider)

        # Verifica se put_object foi chamado
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]

        self.assertEqual(call_kwargs["Bucket"], "raw-imoveis")
        self.assertEqual(call_kwargs["ContentType"], "application/gzip")
        
        # Valida convenção de particionamento Hive: portal=.../year=.../month=.../day=.../
        s3_key: str = call_kwargs["Key"]
        self.assertTrue(s3_key.startswith("portal=quinto_andar/year=2026/month=10/day=21/"))
        self.assertTrue(s3_key.endswith(".jsonl.gz"))
        self.assertIn("test-batch-uuid-1234", s3_key)

        # Valida integridade do conteúdo comprimido
        compressed_body: bytes = call_kwargs["Body"]
        decompressed_data = gzip.decompress(compressed_body).decode("utf-8")
        lines = decompressed_data.strip().split("\n")
        self.assertEqual(len(lines), 1)

        recovered_item = json.loads(lines[0])
        self.assertEqual(recovered_item["portal_listing_id"], "894101874")
        self.assertEqual(recovered_item["payload"]["price"], 500000.0)

        # Valida metadados S3
        metadata = call_kwargs["Metadata"]
        self.assertEqual(metadata["portal"], "quinto_andar")
        self.assertEqual(metadata["batch_id"], "test-batch-uuid-1234")
        self.assertEqual(metadata["item_count"], "1")

    def test_pipeline_disabled_does_nothing(self):
        """Garante que quando desativado, o pipeline não acumula itens nem dispara chamadas."""
        disabled_pipe = MinIOStoragePipeline(enabled=False)
        item = {"source_portal": "quinto_andar", "id": 1}
        ret = disabled_pipe.process_item(item, self.spider)
        self.assertEqual(ret, item)
        self.assertEqual(len(disabled_pipe.items_by_portal), 0)


if __name__ == "__main__":
    unittest.main()
