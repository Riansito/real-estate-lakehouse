-- ==============================================================================
-- DDL: Camada Raw (Landing Zone) - Lakehouse de Imóveis
-- Descrição: Criação do schema 'raw' e da tabela de pouso 'landing_anuncios'
-- para ingestão append-only de lotes JSONB provenientes do Data Lake (S3 / MinIO).
-- ==============================================================================

-- 1. Criação do Schema Raw
CREATE SCHEMA IF NOT EXISTS raw;

-- 2. Tabela de Pouso: raw.landing_anuncios
CREATE TABLE IF NOT EXISTS raw.landing_anuncios (
    id BIGSERIAL PRIMARY KEY,
    source_portal VARCHAR(50) NOT NULL,
    portal_listing_id VARCHAR(100) NOT NULL,
    scraped_at TIMESTAMP WITH TIME ZONE NOT NULL,
    batch_id VARCHAR(100) NOT NULL,
    url TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Índices Estratégicos para Alta Performance de Leitura e Deduplicação
-- Índice por lote de execução (usado pelo loader e pipelines incrementais)
CREATE INDEX IF NOT EXISTS idx_raw_landing_batch 
    ON raw.landing_anuncios (batch_id);

-- Índice temporal pela data/hora da coleta (utilizado pelas janelas diárias do dbt)
CREATE INDEX IF NOT EXISTS idx_raw_landing_scraped_at 
    ON raw.landing_anuncios (scraped_at);

-- Índice composto pela chave natural de negócio no portal (acelera deduplicações e lookups)
CREATE INDEX IF NOT EXISTS idx_raw_landing_portal_listing 
    ON raw.landing_anuncios (source_portal, portal_listing_id);

-- Índice GIN no documento semiestruturado JSONB (otimiza filtros analíticos ad-hoc sobre o payload bruto)
CREATE INDEX IF NOT EXISTS idx_raw_landing_payload_gin 
    ON raw.landing_anuncios USING GIN (payload);

-- 4. Documentação de Metadados e Governança no Catálogo do Banco
COMMENT ON SCHEMA raw IS 'Camada de pouso bruto (Bronze/Landing) do Data Lakehouse de imóveis.';
COMMENT ON TABLE raw.landing_anuncios IS 'Tabela append-only contendo os envelopes brutos de anúncios imobiliários carregados do Data Lake.';
COMMENT ON COLUMN raw.landing_anuncios.id IS 'Identificador sequencial único da linha de pouso no DW.';
COMMENT ON COLUMN raw.landing_anuncios.source_portal IS 'Nome do portal imobiliário de origem (ex: quinto_andar, chaves_na_mao, zap_imoveis).';
COMMENT ON COLUMN raw.landing_anuncios.portal_listing_id IS 'Identificador único do anúncio no portal de origem.';
COMMENT ON COLUMN raw.landing_anuncios.scraped_at IS 'Timestamp UTC em que a extração foi executada pelo scraper.';
COMMENT ON COLUMN raw.landing_anuncios.batch_id IS 'Identificador UUID único do lote de ingestão da esteira.';
COMMENT ON COLUMN raw.landing_anuncios.url IS 'URL canônica pública do imóvel no portal.';
COMMENT ON COLUMN raw.landing_anuncios.payload IS 'Documento semiestruturado JSONB completo contendo todos os atributos extraídos.';
COMMENT ON COLUMN raw.landing_anuncios.created_at IS 'Timestamp de gravação da linha na tabela de pouso.';
