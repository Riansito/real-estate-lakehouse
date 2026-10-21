-- tests/assert_area_util_no_intervalo.sql
-- Validação de Qualidade de Dados: Garante que a área útil privativa, quando preenchida,
-- esteja no intervalo estipulado de sanidade (entre 10 m² e 3.000 m²).
-- Retorna linhas com falha (esperado: 0 linhas).

SELECT
    surrogate_key,
    source_portal,
    portal_listing_id,
    area_util_m2
FROM {{ ref('dim_anuncios_ativos') }}
WHERE area_util_m2 IS NOT NULL
  AND (area_util_m2 < 10 OR area_util_m2 > 3000)
