import socket
import threading
import time
import uuid
import uvicorn
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from emc_board import EMC_Board
from auth import (create_access_token,verify_token,)
from mqtt_config import (get_mqtt_config,update_mqtt_config)
from Battery.qhb import CAN_QHB
from Charger.NPB import NPB_Charger
from mqtt_publish import MQTTPublisher

app = FastAPI(title="PDU API",version="1.0.0",)
battery = CAN_QHB()
charger = NPB_Charger(channel="can1",address=0x03)
emc_board = EMC_Board()

latest_battery_data = None
latest_charger_data = None
data_lock = threading.Lock()

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: str

class MQTTConfigRequest(BaseModel):
    broker: Optional[str] = None
    port: Optional[int] = None
    broker_username: Optional[str] = None
    broker_password: Optional[str] = None

class RemoteShutdownRequest(BaseModel):
    username: Optional[str] = None
    shutoff: bool
    timestamp: Optional[str] = None

def get_hostname():
    return socket.gethostname()

def get_mac_address():
    mac = uuid.getnode()
    return ":".join(f"{(mac >> i) & 0xff:02X}"
        for i in range(40, -1, -8))

def get_time_since_boot():
    return int(time.clock_gettime(time.CLOCK_BOOTTIME))

def battery_task():
    print("[PDU] Starting battery...")
    try:
        if not battery.init_device():
            print(
                "[PDU] Battery initialization failed"
            )
            return
        print(
            "[PDU] Battery CAN initialized"
        )
        battery.start_device()
    except Exception as exc:
        print(
            f"[PDU] Battery thread error: {exc}"
        )

def charger_task():
    global latest_charger_data
    print("[PDU] Starting charger...")
    try:
        if not charger.start_device():
            print(
                "[PDU] Charger initialization failed"
            )
            return
        print(
            "[PDU] Charger initialized"
        )
        while True:
            try:
                data = charger.read_data()
                with data_lock:
                    latest_charger_data = data
            except Exception as exc:
                print(
                    f"[PDU] Charger read error: {exc}"
                )
            time.sleep(2)
    except Exception as exc:
        print(
            f"[PDU] Charger thread error: {exc}"
        )

def update_battery_data():
    global latest_battery_data
    try:
        data = battery.read_data()
        with data_lock:
            latest_battery_data = data
    except Exception as exc:
        print(
            f"[PDU] Battery read error: {exc}"
        )

def get_latest_data():
    with data_lock:
        return {
            "battery": latest_battery_data,
            "charger": latest_charger_data,
        }

mqtt_publisher = MQTTPublisher(
    data_lock=data_lock,
    data_provider=get_latest_data
)
@app.post("/api/v1/auth/token")
def login(request: LoginRequest):
    if (request.username != "admin" or request.password != "admin"):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
        )
    token = create_access_token(username=request.username)
    return {
        "access_token": token,
        "token_type": "bearer",
    }

@app.get(
        "/api/v1/mqtt/config",
    dependencies=[Depends(verify_token)],
)
def read_mqtt_config():
    return get_mqtt_config()
@app.post(
    "/api/v1/mqtt/config",
    dependencies=[Depends(verify_token)],
)
def configure_mqtt(
    request: MQTTConfigRequest
):
    return update_mqtt_config(
        broker=request.broker,
        port=request.port,
        broker_username=request.broker_username,
        broker_password=request.broker_password,
    )

@app.post("/api/v1/remote-shutdown",dependencies=[Depends(verify_token)])
def remote_shutdown(request: RemoteShutdownRequest):

    # Shutdown command must be TRUE
    if request.shutoff is not True:
        raise HTTPException(
            status_code=400,
            detail="shutoff must be true"
        )
    timestamp = request.timestamp
    if timestamp is None:
        timestamp = (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    # Turn OFF all PDU outputs
    result = emc_board.turn_off_all()

    if result is not True:
        raise HTTPException(
            status_code=500,
            detail="Failed to turn off PDU outputs"
        )
    return {
        "username": request.username,
        "shutoff": True,
        "timestamp": timestamp,
        "status": "Remote shutdown executed"
    }

@app.get("/api/v1/status")
def get_status():
    update_battery_data()
    with data_lock:
        batt_data = latest_battery_data
        chgr_data = latest_charger_data

    battery_percentage = 0
    battery_state = "Unknown"
    battery_voltage = 0.0
    battery_current = 0.0
    battery_capacity_full = battery.batt_capacity_full_ah
    battery_capacity_remaining = None

    if batt_data:
        battery_percentage = battery.soc
        battery_state = battery.pack_state
        battery_voltage = battery.pack_voltage
        battery_current = float(
            battery.pack_current
        )
        battery_capacity_full = (
            battery.batt_capacity_full_ah
        )
        battery_capacity_remaining = (
            battery.batt_capacity_remaining_ah
        )

    charger_current = 0.0
    charger_voltage = 0.0
    if chgr_data:
        pdu_chgr = chgr_data.get(
            "pdu_chgr",
            {}
        )
        # Charger output current
        charger_current_raw = pdu_chgr.get(
            "chgr_iout"
        )
        if charger_current_raw is not None:
            try:
                charger_current = float(
                    str(
                        charger_current_raw
                    )
                    .replace("A", "")
                    .strip()
                )
            except (ValueError,TypeError):
                charger_current = 0.0
        # Charger output voltage
        charger_voltage_raw = pdu_chgr.get("chgr_vout_DC")
        if charger_voltage_raw is not None:
            try:
                charger_voltage = float(
                    str(charger_voltage_raw)
                    .replace("V", "")
                    .strip()
                )

            except (
                ValueError,
                TypeError
            ):
                charger_voltage = 0.0

    # LOAD CURRENT

    if battery_state == "Charging":
        load_current = charger_current - battery_current
        if load_current < 0:
         load_current = 0.0

    elif battery_state == "Discharging":
        load_current = abs(battery_current)

    elif battery_state == "Ready":
     load_current = charger_current

    else:
     load_current = 0.0

    load_current = round(load_current,1
    )

    battery_capacity_in_min = None

    if (battery_capacity_remaining is not None and load_current > 0):
        battery_capacity_in_min = int(
        (float(battery_capacity_remaining)
            / load_current) * 60)
        
    timestamp = (datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00","Z"))

    if battery_voltage > 0:
        system_voltage = battery_voltage
    else:
        system_voltage = charger_voltage
    return {
        "hostname": get_hostname(),
        "mac_address": get_mac_address(),
        "timestamp": timestamp,
        "battery_percentage":battery_percentage,
        "battery_state":battery_state,
        "system_voltage":round(system_voltage,1),
        "load_current":load_current,
        "battery_charging_current":battery_current,
        "battery_capacity_in_min":battery_capacity_in_min,
        "time_since_boot_in_sec":get_time_since_boot()
    }

@app.on_event("startup")
def startup():
    print("[PDU] Starting PDU services...")
    battery_thread = threading.Thread(target=battery_task,daemon=True)
    charger_thread = threading.Thread(target=charger_task,daemon=True)
    battery_thread.start()
    charger_thread.start()
    print("[PDU] Battery and charger " "threads started")
    mqtt_publisher.start()
    print("[PDU] MQTT publisher started")    

# MAIN
if __name__ == "__main__":
    uvicorn.run(app,host="0.0.0.0",port=8000)


