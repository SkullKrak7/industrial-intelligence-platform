from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    machine_id: str
    rotational_speed: float = Field(..., ge=1100, le=3000, description="rpm")
    torque: float = Field(..., ge=0, le=100, description="Nm")
    tool_wear: float = Field(..., ge=0, le=300, description="minutes")


class PredictResponse(BaseModel):
    machine_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    anomaly: bool
    threshold: float = Field(..., ge=0.0, le=1.0)
