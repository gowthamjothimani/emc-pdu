from fastapi import APIRouter
from fastapi import Depends
from app.auth import verify_user
from app.config import DEVICE_ID
from app.emc_board import EMC_Board

router = APIRouter()
emc_board = EMC_Board()


@router.get("/status")
def status(user: str = Depends(verify_user)):

    return {
        "device_id": DEVICE_ID,
        "user": user,
        "status": "Running"
    }


@router.get("/battery")
def battery(user: str = Depends(verify_user)):

    return {
        "device_id": DEVICE_ID,
        "battery_voltage": 51.8,
        "battery_soc": 87,
        "battery_current": 3.2
    }


@router.get("/charger")
def charger(user: str = Depends(verify_user)):

    return {
        "device_id": DEVICE_ID,
        "charger_voltage": 51.8,
        "charger_current": 3.2,
        "charger_status": "Chargering"
    }

@router.post("/start")
def start(user: str = Depends(verify_user)):
    emc_board.reset()

    return {
        "device_id": DEVICE_ID,
        "message": "System Started"
    }


@router.post("/stop")
def stop(user: str = Depends(verify_user)):
    result = emc_board.remote_shutoff()

    return {
        "device_id": DEVICE_ID,
        "message": "System Stopped",
        **result,
    }


@router.post("/shutdown")
def shutdown(user: str = Depends(verify_user)):
    result = emc_board.remote_shutoff()

    return {
        "device_id": DEVICE_ID,
        "message": "Remote shutoff requested",
        **result,
    }