-- Name of the macro
{% macro materialization_config() %}
-- The config block instructs dbt to create a table in the database based on this statement
{{ config(
  materialized='table',
  file_format='delta'
) }}
{% endmacro %}