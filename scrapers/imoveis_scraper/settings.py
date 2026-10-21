"""
Scrapy settings para o projeto imoveis_scraper.
Configurações otimizadas para scraping resiliente, seguro e de alta performance.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env localizado na raiz do repositório
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE)

BOT_NAME = "imoveis_scraper"

SPIDER_MODULES = ["imoveis_scraper.spiders"]
NEWSPIDER_MODULE = "imoveis_scraper.spiders"

# ==============================================================================
# CONFIGURAÇÕES DE RESPEITO E ANTI-BLOQUEIO
# ==============================================================================
# Portais imobiliários bloqueiam bots genéricos via robots.txt
ROBOTSTXT_OBEY = False

# Desativar cookies reduz o rastro de sessão entre requisições distribuídas
COOKIES_ENABLED = False

# Rate Limiting: Delay entre requisições com variação randômica (0.5 * delay a 1.5 * delay)
DOWNLOAD_DELAY = 1.5
DOWNLOAD_DELAY_JITTER = 0.5
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# AutoThrottle: Ajusta dinamicamente a velocidade de download baseando-se na latência do servidor
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# Retentativas automáticas em caso de instabilidade ou rate limiting temporário
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 522, 524, 408, 429]

# ==============================================================================
# DOWNLOADER MIDDLEWARES (ROTAÇÃO DE USER-AGENT E INJEÇÃO DE HEADERS)
# ==============================================================================
DOWNLOADER_MIDDLEWARES = {
    # Desativa o UserAgent padrão do Scrapy
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    # Desativa DefaultHeadersMiddleware padrão em prol do BrowserHeadersMiddleware
    "scrapy.downloadermiddlewares.defaultheaders.DefaultHeadersMiddleware": None,
    # Habilita nosso middleware de rotação randômica de User-Agents realistas
    "imoveis_scraper.middlewares.RotateUserAgentMiddleware": 400,
    # Habilita injeção de headers de navegador moderno (Sec-Ch-Ua, Accept-Language, etc.)
    "imoveis_scraper.middlewares.BrowserHeadersMiddleware": 410,
}

# ==============================================================================
# CONFIGURAÇÕES DO AMBIENTE E ARMAZENAMENTO (S3 / MINIO)
# ==============================================================================
AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL_S3")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION_NAME = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "raw-imoveis")
MINIO_PIPELINE_ENABLED = os.getenv("MINIO_PIPELINE_ENABLED", "True").lower() in ("true", "1", "t")

# ==============================================================================
# ITEM PIPELINES (ARMAZENAMENTO EM DATA LAKE)
# ==============================================================================
ITEM_PIPELINES = {
    "imoveis_scraper.pipelines.MinIOStoragePipeline": 300,
}

# Encoding e Compatibilidade
FEED_EXPORT_ENCODING = "utf-8"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# Nível padrão de logs
LOG_LEVEL = os.getenv("SCRAPY_LOG_LEVEL", "INFO")
