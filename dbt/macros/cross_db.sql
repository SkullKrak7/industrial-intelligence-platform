{% macro raw_telemetry_source() %}
    {#- DuckDB reads the CSV directly; BigQuery (and any other warehouse) reads a
        pre-loaded landing table, since only DuckDB has read_csv_auto. The raw
        table is loaded outside dbt by scripts/bq_load_telemetry.sh. -#}
    {% if target.type == 'duckdb' %}
        read_csv_auto(
            '{{ env_var("TELEMETRY_PATH", "data/telemetry_stream.csv") }}',
            header = true,
            auto_detect = true
        )
    {% else %}
        {{ source('raw', 'telemetry_stream') }}
    {% endif %}
{% endmacro %}


{% macro float64_type() -%}
    {#- DOUBLE (DuckDB) and FLOAT64 (BigQuery) are both 64-bit. dbt's built-in
        type_float() maps to 32-bit FLOAT on DuckDB, which would drop precision. -#}
    {%- if target.type == 'bigquery' -%}float64{%- else -%}double{%- endif -%}
{%- endmacro %}
