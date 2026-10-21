-- models/marts/fct_metricas_bairro_diarias.sql
{{
    config(
        materialized='table',
        schema='gold'
    )
}}

WITH base_anuncios AS (
    SELECT * FROM {{ ref('dim_anuncios_ativos') }}
),

agregados AS (
    SELECT
        cidade,
        bairro,
        MAX(bairro_raw) AS bairro_exibicao,
        MAX(estado) AS estado,
        data_coleta AS data_referencia,
        COUNT(*) AS total_anuncios_ativos,
        ROUND(AVG(preco), 2) AS preco_medio,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY preco)::NUMERIC(12, 2) AS preco_mediano,
        MIN(preco) AS preco_minimo,
        MAX(preco) AS preco_maximo,
        ROUND(AVG(preco_m2), 2) AS preco_m2_medio,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY preco_m2)::NUMERIC(12, 2) AS preco_m2_mediano,
        ROUND(AVG(area_util_m2), 2) AS area_media_m2,
        ROUND(AVG(quartos), 1) AS quartos_medio,
        COUNT(CASE WHEN status_oportunidade = 'ABAIXO_DA_MEDIA' THEN 1 END) AS total_oportunidades_abaixo_media,
        NOW() AS atualizado_em
    FROM base_anuncios
    GROUP BY cidade, bairro, data_coleta
),

final AS (
    SELECT
        MD5(cidade || '-' || bairro || '-' || data_referencia::TEXT) AS id_metrica,
        cidade,
        bairro,
        bairro_exibicao,
        estado,
        data_referencia,
        total_anuncios_ativos,
        preco_medio,
        preco_mediano,
        preco_minimo,
        preco_maximo,
        preco_m2_medio,
        preco_m2_mediano,
        area_media_m2,
        quartos_medio,
        total_oportunidades_abaixo_media,
        atualizado_em
    FROM agregados
)

SELECT * FROM final
