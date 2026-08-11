from datetime import datetime, timedelta, timezone
import socket
import time
import uuid
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from .auth import authenticate_user, create_access_token, verify_acv_token
from .config import ACCESS_TOKEN_EXPIRE_MINUTES, HOSTNAME
from .hardware import HardwareService
from .mqtt_config import load_mqtt_config, save_mqtt_config
from .schemas import MQTTConfig, RemoteShutoffRequest, RemoteShutoffResponse, StatusResponse, TokenResponse
from .emc_board import EMC_Board

app = FastAPI(title="PDU API", version="1.0")
emc_board = EMC_Board()
hardware_service = HardwareService()


def format_mac_address() -> str:
    mac_value = uuid.getnode()
    mac_hex = f"{mac_value:012X}"
    return ":".join(mac_hex[i : i + 2] for i in range(0, 12, 2))


def get_time_since_boot() -> int:
    try:
        import psutil

        return int(time.time() - psutil.boot_time())
    except Exception:
        return int(time.monotonic())


@app.post("/token", response_model=TokenResponse)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    if not authenticate_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.on_event("startup")
def on_startup():
    hardware_service.start()


@app.on_event("shutdown")
def on_shutdown():
    hardware_service.stop()


@app.post("/config/mqtt", response_model=MQTTConfig, dependencies=[Depends(verify_acv_token)])
def update_mqtt_config(config: MQTTConfig):
    saved_config = save_mqtt_config(config.dict())
    hardware_service.reload_config(saved_config)
    return saved_config


@app.get("/config/mqtt", response_model=MQTTConfig, dependencies=[Depends(verify_acv_token)])
def get_mqtt_config():
    return load_mqtt_config()


def _extract_status(payload: dict) -> dict:
    batt = payload.get("pdu_batt", {})
    chgr = payload.get("pdu_chgr", {})

    return {
        "battery_percentage": int(batt.get("batt_can_params", {}).get("batt_soc", "0%").rstrip("%")) if batt else 0,
        "battery_state": batt.get("batt_can_params", {}).get("batt_state", "Unknown") if batt else "Unknown",
        "system_voltage": float(batt.get("batt_can_params", {}).get("batt_voltage", "0V").rstrip("V")) if batt else 0.0,
        "load_current": float(batt.get("batt_can_params", {}).get("batt_current", "0A").rstrip("A")) if batt else 0.0,
        "battery_charging_current": float(chgr.get("pdu_chgr", {}).get("chgr_iout", "0A").rstrip("A")) if chgr else 0.0,
        "battery_capacity_in_min": int(chgr.get("pdu_chgr", {}).get("chgr_model_name", "0")) if chgr else 0,
    }


@app.get("/status", response_model=StatusResponse, dependencies=[Depends(verify_acv_token)])
def get_status():
    latest = hardware_service.get_latest_status()
    battery_payload = latest.get("battery", {})
    charger_payload = latest.get("charger", {})
    mqtt_status = _extract_status({**battery_payload, **charger_payload})

    return {
        "hostname": HOSTNAME,
        "mac_address": format_mac_address(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "battery_percentage": mqtt_status["battery_percentage"],
        "battery_state": mqtt_status["battery_state"],
        "system_voltage": mqtt_status["system_voltage"],
        "load_current": mqtt_status["load_current"],
        "battery_charging_current": mqtt_status["battery_charging_current"],
        "battery_capacity_in_min": mqtt_status["battery_capacity_in_min"],
        "time_since_boot_in_sec": get_time_since_boot(),
    }


@app.post("/remote-shutoff", response_model=RemoteShutoffResponse, dependencies=[Depends(verify_acv_token)])
def remote_shutoff(request: RemoteShutoffRequest):
    if request.turn_off_command:
        success = emc_board.turn_off_all()
        detail = emc_board.last_error or "All outputs turned off"
        status_text = "shutdown_initiated" if success else "shutdown_failed"
    else:
        success = False
        detail = "turn_off_command must be true to execute shutoff"
        status_text = "shutdown_skipped"

    return {
        "username": request.username,
        "turn_off_command": request.turn_off_command,
        "timestamp": request.timestamp,
        "success": success,
        "status": status_text,
        "detail": detail,
    }
