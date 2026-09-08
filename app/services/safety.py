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
        if not device.get("is_nvme", True):
            raise ValueError("只允许测试 NVMe Namespace 设备")
        if not device.get("is_ssd", True):
            raise ValueError("只允许测试非旋转 NVMe SSD")
        if device.get("is_system_disk"):
            raise ValueError("禁止测试系统盘")
        if device.get("mounted"):
            raise ValueError("禁止测试已挂载的设备或包含已挂载分区的设备")
        if device.get("in_use"):
            raise ValueError("设备正在被系统占用，禁止测试")
        if device.get("has_partitions") or device.get("has_filesystem"):
            raise ValueError("禁止测试包含分区或文件系统的设备")
        if device.get("read_only"):
            raise ValueError("设备处于只读状态，禁止测试")
        destructive = is_destructive(request.test_type, request.parameters)
        if destructive:
            if not request.destructive_confirmed or request.confirmation_device != request.device:
                raise ValueError("破坏性测试必须确认风险并手工输入完整目标设备名")
        return device
