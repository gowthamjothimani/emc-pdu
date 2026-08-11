from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MQTTConfig(BaseModel):
    broker: str
    port: int
    broker_username: str
    broker_password: str
    battery_topic: str
    charger_topic: str | None = None


class StatusResponse(BaseModel):
    hostname: str
    mac_address: str
    timestamp: str
    battery_percentage: int
    battery_state: str
    system_voltage: float
    load_current: float
    battery_charging_current: float
    battery_capacity_in_min: int
    time_since_boot_in_sec: int


class RemoteShutoffRequest(BaseModel):
    username: str
    turn_off_command: bool
    timestamp: str


class RemoteShutoffResponse(BaseModel):
    username: str
    turn_off_command: bool
    timestamp: str
    success: bool
    status: str
    detail: str
