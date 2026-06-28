with source as (
    select * from {{ raw_telemetry_source() }}
)

select
    cast(timestamp        as timestamp)               as reading_at,
    cast(machine_id       as {{ dbt.type_string() }}) as machine_id,
    cast(temperature      as {{ float64_type() }})    as temperature_c,
    cast(vibration        as {{ float64_type() }})    as vibration_g,
    cast(pressure         as {{ float64_type() }})    as pressure_bar,
    cast(rotational_speed as {{ float64_type() }})    as rotational_speed_rpm,
    cast(torque           as {{ float64_type() }})    as torque_nm,
    cast(tool_wear        as {{ float64_type() }})    as tool_wear_min
from source
where machine_id is not null
