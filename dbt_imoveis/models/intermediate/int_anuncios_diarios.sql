-- models/intermediate/int_anuncios_diarios.sql
{{
    config(
        materialized='table',
        schema='silver'
    )
}}

WITH staging AS (
    SELECT * FROM {{ ref('stg_anuncios') }}
),

-- Filtros de sanidade e padronização inicial
cleaned AS (
    SELECT
        landing_id,
        source_portal,
        portal_listing_id,
        batch_id,
        url,
        TRIM(titulo) AS titulo,
        preco,
        valor_condominio,
        valor_iptu,
        -- Saneamento de área útil: entre 10 m² e 3000 m²
        CASE 
            WHEN area_util_m2 BETWEEN 10 AND 3000 THEN area_util_m2 
            ELSE NULL 
        END AS area_util_m2,
        -- Saneamento de quartos: entre 0 e 20
        CASE 
            WHEN quartos BETWEEN 0 AND 20 THEN quartos 
            ELSE NULL 
        END AS quartos,
        -- Saneamento de banheiros: mínimo de 1, teto de 20
        CASE 
            WHEN banheiros IS NULL OR banheiros < 1 THEN 1 
            WHEN banheiros > 20 THEN 20 
            ELSE banheiros 
        END AS banheiros,
        -- Saneamento de vagas: não-negativo
        CASE 
            WHEN vagas IS NULL OR vagas < 0 THEN 0 
            WHEN vagas > 20 THEN 20
            ELSE vagas 
        END AS vagas,
        TRIM(rua) AS rua,
        -- Normalização de bairro (caixa baixa e remoção de acentos para agrupamento padronizado)
        TRIM(bairro) AS bairro_raw,
        TRANSLATE(
            LOWER(TRIM(bairro)),
            'áàâãäéèêëíìîïóòôõöúùûüçñ',
            'aaaaaeeeeiiiiooooouuuucn'
        ) AS bairro,
        TRIM(cidade) AS cidade,
        UPPER(TRIM(estado)) AS estado,
        TRIM(cep) AS cep,
        latitude,
        longitude,
        comodidades,
        tipo_anunciante,
        scraped_at,
        CAST(scraped_at AS DATE) AS data_coleta,
        carregado_em
    FROM staging
    WHERE 
        -- Filtro de sanidade financeira: preços válidos para venda entre 50k e 100M
        preco BETWEEN 50000 AND 100000000
        -- Filtro de localidade mínima obrigatória
        AND cidade IS NOT NULL AND TRIM(cidade) != ''
),

-- Nível 1: Deduplicação Técnica de Coleta (Idempotência por portal, anúncio e dia)
dedup_coleta AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY source_portal, portal_listing_id, data_coleta
            ORDER BY scraped_at DESC, landing_id DESC
        ) AS row_num
    FROM cleaned
),

-- Seleção dos registros diários válidos com surrogate key e fingerprint canônico
final AS (
    SELECT
        -- Chave substituta do anúncio no portal
        MD5(source_portal || '-' || portal_listing_id) AS surrogate_key,
        -- Fingerprint canônico do imóvel real (Nível 2 - resolução entre portais)
        MD5(
            COALESCE(LOWER(TRIM(cidade)), '') || '-' ||
            COALESCE(bairro, '') || '-' ||
            COALESCE(LOWER(TRIM(rua)), '') || '-' ||
            COALESCE(ROUND(area_util_m2, 0)::TEXT, '0') || '-' ||
            COALESCE(quartos::TEXT, '0') || '-' ||
            COALESCE(vagas::TEXT, '0')
        ) AS property_fingerprint,
        landing_id,
        source_portal,
        portal_listing_id,
        batch_id,
        url,
        titulo,
        preco,
        valor_condominio,
        valor_iptu,
        area_util_m2,
        ROUND(preco / NULLIF(area_util_m2, 0), 2) AS preco_m2,
        quartos,
        banheiros,
        vagas,
        rua,
        bairro,
        bairro_raw,
        cidade,
        estado,
        cep,
        latitude,
        longitude,
        comodidades,
        tipo_anunciante,
        data_coleta,
        scraped_at,
        carregado_em
    FROM dedup_coleta
    WHERE row_num = 1
)

SELECT * FROM final
