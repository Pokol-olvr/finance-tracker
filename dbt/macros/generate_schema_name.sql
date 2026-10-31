{# A sémanév maga a silver vagy gold, a dbt alapértelmezett előtagja nélkül. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
