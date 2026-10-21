-- tests/assert_precos_no_intervalo_sanidade.sql
-- Validação de Qualidade de Dados: Garante que os preços de venda em dim_anuncios_ativos
-- estejam rigorosamente dentro do intervalo plausível de negócio (R$ 50.000 a R$ 100.000.000).
-- Retorna linhas com falha (esperado: 0 linhas).

SELECT
    surrogate_key,
    source_portal,
    portal_listing_id,
    preco
FROM {{ ref('dim_anuncios_ativos') }}
WHERE preco < 50000 OR preco > 100000000
