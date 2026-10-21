"""
Modelos de dados (Items) para o scraper de imóveis.
Define a estrutura padronizada dos dados brutos extraídos antes de serem enviados ao Data Lake.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import scrapy


class RawPropertyItem(scrapy.Item):
    """
    Envelope padronizado para os dados brutos de anúncios imobiliários coletados.
    Segue rigorosamente as especificações de governança e metadados definidas na arquitetura.
    """
    source_portal = scrapy.Field()      # Nome do portal de origem (ex: zap_imoveis, viva_real, etc)
    portal_listing_id = scrapy.Field()  # Identificador único do anúncio no portal
    scraped_at = scrapy.Field()         # Timestamp UTC da coleta no formato ISO 8601
    batch_id = scrapy.Field()           # Identificador único da execução (UUID)
    url = scrapy.Field()                # URL completa do anúncio
    payload = scrapy.Field()            # Dicionário JSON completo com os dados brutos da listagem
