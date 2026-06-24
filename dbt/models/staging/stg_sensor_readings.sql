with source as (
    select *
    from read_csv_auto(
        '{{ env_var("TELEMETRY_PATH", "../data/telemetry_stream.csv") }}',
        header = true,
        auto_detect = true
    )
)

select
    cast(timestamp        as timestamp)  as reading_at,
    cast(machine_id       as varchar)    as machine_id,
    cast(temperature      as double)     as temperature_c,
    cast(vibration        as double)     as vibration_g,
    cast(pressure         as double)     as pressure_bar,
    cast(rotational_speed as double)     as rotational_speed_rpm,
    cast(torque           as double)     as torque_nm,
    cast(tool_wear        as double)     as tool_wear_min
from source
where machine_id is not null
