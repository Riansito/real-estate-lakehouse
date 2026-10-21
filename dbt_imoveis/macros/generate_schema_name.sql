{% macro generate_schema_name(custom_schema_name, node) -%}
    {#
        Sobrescreve a convenção padrão do dbt para respeitar rigorosamente os schemas
        do Data Lakehouse: 'staging', 'silver' e 'gold', sem prefixos indesejados.
    #}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
