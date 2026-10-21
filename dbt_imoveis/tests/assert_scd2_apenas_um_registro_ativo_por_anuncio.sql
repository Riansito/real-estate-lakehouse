-- tests/assert_scd2_apenas_um_registro_ativo_por_anuncio.sql
-- Validação de Integridade Temporal SCD Tipo 2: Garante que cada anúncio
-- (surrogate_key) possua no máximo um único registro ativo (dbt_valid_to IS NULL).
-- Retorna surrogate_keys com múltiplos registros ativos (esperado: 0 linhas).

SELECT
    surrogate_key,
    COUNT(*) AS total_registros_ativos
FROM {{ ref('snp_historico_precos') }}
WHERE dbt_valid_to IS NULL
GROUP BY surrogate_key
HAVING COUNT(*) > 1
