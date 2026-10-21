"""
Spider de verificação de sanidade para testar os middlewares de User-Agent e Headers.
Faz requisições para o endpoint de echo httpbin.org para validar que os cabeçalhos reais
estão sendo injetados e alternados corretamente.
"""
import json
import scrapy
from loguru import logger


class CheckHeadersSpider(scrapy.Spider):
    name = "check_headers"
    allowed_domains = ["httpbin.org"]
    start_urls = [
        "https://httpbin.org/headers",
        "https://httpbin.org/headers",
    ]

    custom_settings = {
        "LOG_LEVEL": "INFO",
    }

    def parse(self, response):
        try:
            data = json.loads(response.text)
            headers = data.get("headers", {})
            user_agent = headers.get("User-Agent", "N/A")
            sec_ch_ua = headers.get("Sec-Ch-Ua", "N/A")
            accept_lang = headers.get("Accept-Language", "N/A")

            logger.info("=" * 60)
            logger.info("VERIFICAÇÃO DE MIDDLEWARES - HTTPBIN ECHO:")
            logger.info(f"URL: {response.url}")
            logger.info(f"User-Agent recebido: {user_agent}")
            logger.info(f"Sec-Ch-Ua recebido: {sec_ch_ua}")
            logger.info(f"Accept-Language recebido: {accept_lang}")
            logger.info("=" * 60)

            yield {
                "url": response.url,
                "user_agent": user_agent,
                "headers": headers,
            }
        except Exception as e:
            logger.error(f"Erro ao processar resposta: {e}")
