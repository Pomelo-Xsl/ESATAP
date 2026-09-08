from fastapi import APIRouter, HTTPException

from app.services.device import DeviceService, validate_namespace_path
from app.services.smart import SmartService


router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("")
def list_devices():
    return DeviceService().scan()


@router.get("/{device:path}/smart")
def get_smart(device: str):
    path = "/" + device if not device.startswith("/") else device
    try:
        validate_namespace_path(path)
        if not DeviceService().get(path):
            raise ValueError("设备不存在或无法确认")
        return SmartService().collect(path)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

