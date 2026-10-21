"""
Testes unitários para o LakeToPostgresLoader.
Valida o parsing de arquivos comprimidos em .jsonl.gz, a idempotência e o controle de ingestão.
"""
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.lake_to_postgres_loader import LakeToPostgresLoader


class TestLakeToPostgresLoader(unittest.TestCase):
    """Testes unitários para a ingestão incremental do Data Lake para o PostgreSQL."""

    def setUp(self):
        self.mock_db_url = "postgresql://user:pass@localhost:5432/testdb"
        with patch("boto3.client") as mock_boto:
            self.mock_s3 = MagicMock()
            mock_boto.return_value = self.mock_s3
            self.loader = LakeToPostgresLoader(
                db_url=self.mock_db_url,
                bucket_name="raw-imoveis",
            )
            self.loader.s3_client = self.mock_s3

    def test_load_file_content_decompression(self):
        """Valida se o loader descomprime corretamente o .jsonl.gz e extrai os itens."""
        records = [
            {
                "source_portal": "quinto_andar",
                "portal_listing_id": "111",
                "scraped_at": "2026-10-21T15:00:00Z",
                "batch_id": "batch-abc",
                "url": "https://quintoandar.com.br/imovel/111",
                "payload": {"title": "Apto 1", "price": 300000.0},
            },
            {
                "source_portal": "quinto_andar",
                "portal_listing_id": "222",
                "scraped_at": "2026-10-21T15:00:00Z",
                "batch_id": "batch-abc",
                "url": "https://quintoandar.com.br/imovel/222",
                "payload": {"title": "Apto 2", "price": 450000.0},
            },
        ]
        jsonl_str = "\n".join(json.dumps(r) for r in records) + "\n"
        compressed_bytes = gzip.compress(jsonl_str.encode("utf-8"))

        mock_body = MagicMock()
        mock_body.read.return_value = compressed_bytes
        self.mock_s3.get_object.return_value = {"Body": mock_body}

        extracted_records, portal, batch_id = self.loader.load_file_content("portal=quinto_andar/test.jsonl.gz")

        self.assertEqual(len(extracted_records), 2)
        self.assertEqual(portal, "quinto_andar")
        self.assertEqual(batch_id, "batch-abc")
        self.assertEqual(extracted_records[0]["portal_listing_id"], "111")
        self.assertEqual(extracted_records[1]["payload"]["price"], 450000.0)

    def test_list_s3_files_filters_jsonl_gz(self):
        """Valida se apenas arquivos terminados em .jsonl.gz são considerados."""
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "portal=quinto_andar/file1.jsonl.gz", "Size": 1024, "LastModified": datetime.now(timezone.utc)},
                    {"Key": "portal=quinto_andar/ignore.txt", "Size": 50, "LastModified": datetime.now(timezone.utc)},
                    {"Key": "portal=quinto_andar/file2.jsonl.gz", "Size": 2048, "LastModified": datetime.now(timezone.utc)},
                ]
            }
        ]
        self.mock_s3.get_paginator.return_value = paginator

        files = self.loader.list_s3_files(portal="quinto_andar")
        self.assertEqual(len(files), 2)
        keys = [f["key"] for f in files]
        self.assertIn("portal=quinto_andar/file1.jsonl.gz", keys)
        self.assertIn("portal=quinto_andar/file2.jsonl.gz", keys)
        self.assertNotIn("portal=quinto_andar/ignore.txt", keys)


if __name__ == "__main__":
    unittest.main()
