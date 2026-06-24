with features as (
    select * from {{ ref('int_feature_engineering') }}
)

select
    machine_id,
    count(*)                                      as total_readings,
    round(avg(temperature_c), 2)                  as avg_temperature_c,
    round(avg(vibration_g), 4)                    as avg_vibration_g,
    round(avg(pressure_bar), 2)                   as avg_pressure_bar,
    round(avg(rotational_speed_rpm), 1)           as avg_rotational_speed_rpm,
    round(avg(torque_nm), 2)                      as avg_torque_nm,
    round(avg(tool_wear_min), 2)                  as avg_tool_wear_min,
    round(max(tool_wear_min), 2)                  as peak_tool_wear_min,
    round(avg(power_kw), 4)                       as avg_power_kw,
    round(max(power_kw), 4)                       as peak_power_kw,
    round(avg(tool_wear_pct), 4)                  as avg_tool_wear_pct,
    sum(case when sensor_fault then 1 else 0 end) as sensor_fault_count,
    round(
        sum(case when sensor_fault then 1 else 0 end) * 1.0 / count(*),
        4
    )                                             as sensor_fault_rate,
    max(reading_at)                               as last_reading_at
from features
group by machine_id
