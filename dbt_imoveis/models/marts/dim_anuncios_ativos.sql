-- models/marts/dim_anuncios_ativos.sql
{{
    config(
        materialized='table',
        schema='gold'
    )
}}

WITH anuncios_recentes AS (
    SELECT 
        *,
        ROW_NUMBER() OVER (
            PARTITION BY surrogate_key 
            ORDER BY scraped_at DESC
        ) AS rank_recente
    FROM {{ ref('int_anuncios_diarios') }}
),

anuncios_ativos AS (
    SELECT
        a.surrogate_key,
        a.property_fingerprint,
        a.source_portal,
        a.portal_listing_id,
        a.batch_id,
        a.url,
        a.titulo,
        a.preco,
        a.valor_condominio,
        a.valor_iptu,
        a.area_util_m2,
        a.preco_m2,
        a.quartos,
        a.banheiros,
        a.vagas,
        a.rua,
        a.bairro,
        a.bairro_raw,
        a.cidade,
        a.estado,
        a.cep,
        a.latitude,
        a.longitude,
        a.comodidades,
        a.tipo_anunciante,
        a.scraped_at AS ultima_coleta,
        a.data_coleta,
        h.dbt_valid_from AS preco_vigente_desde,
        a.carregado_em
    FROM anuncios_recentes a
    INNER JOIN {{ ref('snp_historico_precos') }} h
        ON a.surrogate_key = h.surrogate_key
        AND h.dbt_valid_to IS NULL
    WHERE a.rank_recente = 1
),

-- Enriquecimento com métricas de bairro para identificar oportunidades de compra
com_metricas_bairro AS (
    SELECT
        *,
        ROUND(AVG(preco_m2) OVER (PARTITION BY cidade, bairro), 2) AS preco_m2_medio_bairro,
        ROUND(
            (preco_m2 - AVG(preco_m2) OVER (PARTITION BY cidade, bairro)) 
            / NULLIF(AVG(preco_m2) OVER (PARTITION BY cidade, bairro), 0) * 100, 
            2
        ) AS diferenca_percentual_bairro,
        CASE 
            WHEN (preco_m2 - AVG(preco_m2) OVER (PARTITION BY cidade, bairro)) 
                 / NULLIF(AVG(preco_m2) OVER (PARTITION BY cidade, bairro), 0) <= -0.15 
            THEN 'ABAIXO_DA_MEDIA'
            WHEN (preco_m2 - AVG(preco_m2) OVER (PARTITION BY cidade, bairro)) 
                 / NULLIF(AVG(preco_m2) OVER (PARTITION BY cidade, bairro), 0) >= 0.15 
            THEN 'ACIMA_DA_MEDIA'
            ELSE 'REGULAR'
        END AS status_oportunidade
    FROM anuncios_ativos
)

SELECT * FROM com_metricas_bairro
