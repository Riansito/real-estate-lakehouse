-- tests/assert_banheiros_e_vagas_positivos.sql
-- Validação de Sanidade Estrutural: Garante que todo imóvel possua pelo menos 1 banheiro
-- e que a contagem de vagas de garagem não seja negativa.
-- Retorna linhas que violem as regras físicas (esperado: 0 linhas).

SELECT
    surrogate_key,
    source_portal,
    portal_listing_id,
    banheiros,
    vagas
FROM {{ ref('dim_anuncios_ativos') }}
WHERE banheiros < 1
   OR vagas < 0
