"""
Middlewares do Scrapy para o projeto de scraping de imóveis.
Implementa:
1. RotateUserAgentMiddleware: Rotação dinâmica de User-Agents realistas (Chrome, Firefox, Safari, Edge).
2. BrowserHeadersMiddleware: Injeção de headers realistas de navegadores para contorno de proteções anti-bot.
"""
import random
from typing import List, Optional
from scrapy import signals, Spider
from scrapy.http import Request, Response
from loguru import logger

# Fallback curado com User-Agents modernos de desktop (Windows, macOS, Linux)
FALLBACK_USER_AGENTS = [
    # Chrome on Windows / Mac / Linux
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    # Firefox on Windows / Mac / Linux
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
]


class RotateUserAgentMiddleware:
    """
    Middleware responsável por alternar aleatoriamente o User-Agent em cada requisição.
    Utiliza uma lista de User-Agents modernos ou fake-useragent com fallback resiliente.
    """

    def __init__(self, user_agents: Optional[List[str]] = None, use_fake_useragent: bool = True):
        self.user_agents = user_agents or FALLBACK_USER_AGENTS
        self.use_fake_useragent = use_fake_useragent
        self._fua = None

        if self.use_fake_useragent:
            try:
                from fake_useragent import UserAgent
                self._fua = UserAgent(
                    browsers=["chrome", "firefox", "edge", "safari"],
                    os=["windows", "macos", "linux"],
                    fallback=random.choice(FALLBACK_USER_AGENTS)
                )
            except Exception as e:
                logger.warning(f"fake-useragent fallback ativado ({e}).")
                self._fua = None

    @classmethod
    def from_crawler(cls, crawler):
        user_agents = crawler.settings.getlist("USER_AGENTS", None)
        use_fake_useragent = crawler.settings.getbool("USE_FAKE_USERAGENT", True)
        return cls(user_agents=user_agents, use_fake_useragent=use_fake_useragent)

    def process_request(self, request: Request, spider: Optional[Spider] = None) -> None:
        # Se a requisição já tiver um User-Agent fixado explicitamente, respeita
        if request.meta.get("keep_user_agent", False):
            return

        selected_ua: str
        if self._fua is not None:
            try:
                selected_ua = self._fua.random
            except Exception:
                selected_ua = random.choice(self.user_agents)
        else:
            selected_ua = random.choice(self.user_agents)

        request.headers[b"User-Agent"] = selected_ua.encode("utf-8")


class BrowserHeadersMiddleware:
    """
    Middleware que injeta cabeçalhos HTTP realistas de navegador moderno (Sec-Ch-Ua, Accept-Language, etc.),
    reduzindo bloqueios por WAFs e heurísticas anti-bot.
    """

    DEFAULT_HEADERS = {
        b"Accept": b"text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        b"Accept-Language": b"pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        b"Accept-Encoding": b"gzip, deflate, br",
        b"Sec-Ch-Ua": b'"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
        b"Sec-Ch-Ua-Mobile": b"?0",
        b"Sec-Ch-Ua-Platform": b'"Linux"',
        b"Sec-Fetch-Dest": b"document",
        b"Sec-Fetch-Mode": b"navigate",
        b"Sec-Fetch-Site": b"same-origin",
        b"Sec-Fetch-User": b"?1",
        b"Upgrade-Insecure-Requests": b"1",
    }

    def __init__(self, default_headers: Optional[dict] = None):
        self.default_headers = default_headers or self.DEFAULT_HEADERS

    @classmethod
    def from_crawler(cls, crawler):
        custom_headers = crawler.settings.get("DEFAULT_BROWSER_HEADERS", None)
        if custom_headers:
            encoded_headers = {
                k.encode("utf-8") if isinstance(k, str) else k:
                v.encode("utf-8") if isinstance(v, str) else v
                for k, v in custom_headers.items()
            }
            return cls(default_headers=encoded_headers)
        return cls()

    def process_request(self, request: Request, spider: Optional[Spider] = None) -> None:
        for header, value in self.default_headers.items():
            # Injeta apenas se não tiver sido especificado explicitamente na requisição
            if header not in request.headers or request.headers[header] == b"en":
                request.headers[header] = value


class ImoveisScraperSpiderMiddleware:
    """Middleware padrão de Spider do Scrapy."""

    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response: Response, spider: Spider):
        return None

    def process_spider_output(self, response: Response, result, spider: Spider):
        for i in result:
            yield i

    def process_spider_exception(self, response: Response, exception: Exception, spider: Spider):
        pass

    async def process_start(self, start):
        async for item_or_request in start:
            yield item_or_request

    def spider_opened(self, spider: Spider):
        spider.logger.info(f"Spider iniciado: {spider.name}")
