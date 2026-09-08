from __future__ import annotations

from app.schemas.tasks import TestCreate
from app.services.device import DeviceService, validate_namespace_path
from app.services.fio import is_destructive


class SafetyService:
    def __init__(self, devices: DeviceService | None = None):
        self.devices = devices or DeviceService()

    def validate(self, request: TestCreate) -> dict:
        validate_namespace_path(request.device)
        device = self.devices.get(request.device)
        if not device:
            raise ValueError("无法确认目标设备，已拒绝执行")
        if device.get("is_system_disk"):
            raise ValueError("禁止测试系统盘")
        destructive = is_destructive(request.test_type, request.parameters)
        if destructive:
            if not request.destructive_confirmed or request.confirmation_device != request.device:
                raise ValueError("破坏性测试必须确认风险并手工输入完整目标设备名")
            if device.get("mounted"):
                raise ValueError("禁止对已挂载设备执行写测试")
            if device.get("has_partitions") or device.get("has_filesystem"):
                raise ValueError("禁止对包含分区或文件系统的设备执行破坏性测试")
        return device
