-- tests/assert_preco_m2_positivo.sql
-- Validação de Qualidade de Dados: Garante que o preço por m² calculado seja estritamente positivo (> 0).
-- Retorna linhas com falha (esperado: 0 linhas).

SELECT
    surrogate_key,
    preco,
    area_util_m2,
    preco_m2
FROM {{ ref('dim_anuncios_ativos') }}
WHERE preco_m2 IS NOT NULL
  AND preco_m2 <= 0
