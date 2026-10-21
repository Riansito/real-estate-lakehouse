{% snapshot snp_historico_precos %}

{{
    config(
        target_schema='gold',
        unique_key='surrogate_key',
        strategy='check',
        check_cols=['preco', 'valor_condominio', 'valor_iptu']
    )
}}

SELECT
    surrogate_key,
    source_portal,
    portal_listing_id,
    preco,
    valor_condominio,
    valor_iptu,
    scraped_at
FROM {{ ref('int_anuncios_diarios') }}

{% endsnapshot %}
