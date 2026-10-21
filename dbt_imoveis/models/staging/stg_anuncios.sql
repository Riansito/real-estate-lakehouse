-- models/staging/stg_anuncios.sql
{{
    config(
        materialized='view',
        schema='staging'
    )
}}

WITH source AS (
    SELECT * FROM {{ source('raw', 'landing_anuncios') }}
),

parsed AS (
    SELECT
        id AS landing_id,
        source_portal,
        portal_listing_id,
        scraped_at,
        batch_id,
        url,
        payload->>'title' AS titulo,
        CAST(NULLIF(NULLIF(TRIM(payload->>'price'), ''), 'None') AS NUMERIC(12, 2)) AS preco,
        CAST(NULLIF(NULLIF(TRIM(payload->>'condo_fee'), ''), 'None') AS NUMERIC(10, 2)) AS valor_condominio,
        CAST(NULLIF(NULLIF(TRIM(payload->>'iptu'), ''), 'None') AS NUMERIC(10, 2)) AS valor_iptu,
        CAST(NULLIF(NULLIF(TRIM(payload->>'usable_area_m2'), ''), 'None') AS NUMERIC(8, 2)) AS area_util_m2,
        CAST(NULLIF(NULLIF(TRIM(payload->>'bedrooms'), ''), 'None') AS INTEGER) AS quartos,
        CAST(NULLIF(NULLIF(TRIM(payload->>'bathrooms'), ''), 'None') AS INTEGER) AS banheiros,
        CAST(NULLIF(NULLIF(TRIM(payload->>'parking_spots'), ''), 'None') AS INTEGER) AS vagas,
        payload->'address'->>'street' AS rua,
        payload->'address'->>'neighborhood' AS bairro,
        payload->'address'->>'city' AS cidade,
        payload->'address'->>'state' AS estado,
        payload->'address'->>'zip_code' AS cep,
        CAST(NULLIF(NULLIF(TRIM(payload->'address'->>'latitude'), ''), 'None') AS DOUBLE PRECISION) AS latitude,
        CAST(NULLIF(NULLIF(TRIM(payload->'address'->>'longitude'), ''), 'None') AS DOUBLE PRECISION) AS longitude,
        payload->'amenities' AS comodidades,
        payload->>'advertiser_type' AS tipo_anunciante,
        created_at AS carregado_em
    FROM source
)

SELECT * FROM parsed
