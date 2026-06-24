with base as (
    select * from {{ ref('stg_sensor_readings') }}
)

select
    reading_at,
    machine_id,
    temperature_c,
    vibration_g,
    pressure_bar,
    rotational_speed_rpm,
    torque_nm,
    tool_wear_min,

    -- Mechanical power output (kW): P = (rpm × Nm) / 9550
    round((rotational_speed_rpm * torque_nm) / 9550.0, 4) as power_kw,

    -- Tool wear as a fraction of the 253-min service limit
    round(tool_wear_min / 253.0, 4) as tool_wear_pct,

    -- Sensor-health fault flag matching train_twin_model.py thresholds
    case
        when temperature_c > 87
          or vibration_g   > 4.1
          or pressure_bar  > 91
        then true
        else false
    end as sensor_fault
from base
