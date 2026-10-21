-- tests/assert_total_oportunidades_coerente.sql
-- Validação de Coerência de Métricas de Negócio: Garante que o total de oportunidades
-- abaixo da média nunca supere o total geral de anúncios ativos no bairro.
-- Retorna linhas com inconsistências (esperado: 0 linhas).

SELECT
    id_metrica,
    cidade,
    bairro,
    data_referencia,
    total_anuncios_ativos,
    total_oportunidades_abaixo_media
FROM {{ ref('fct_metricas_bairro_diarias') }}
WHERE total_oportunidades_abaixo_media > total_anuncios_ativos
   OR total_anuncios_ativos <= 0
