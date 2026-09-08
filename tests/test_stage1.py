import json
from unittest.mock import patch

import pytest

from app.schemas.tasks import FioParameters, TestCreate as CreateSchema
from app.services.device import DeviceService, validate_namespace_path
from app.services.fio import FioCommandBuilder
from app.services.safety import SafetyService
from app.services.smart import parse_smart_json


def device(**overrides):
    base = {"name": "/dev/nvme2n1", "is_system_disk": False, "mounted": False, "has_partitions": False, "has_filesystem": False}
    base.update(overrides)
    return base


class FakeDevices:
    def __init__(self, value): self.value = value
    def get(self, _): return self.value


def request(test_type="rand_read_4k", **kwargs):
    return CreateSchema(name="test", device="/dev/nvme2n1", test_type=test_type, parameters=FioParameters(), **kwargs)


def test_fio_command_is_argument_list_and_has_defaults(tmp_path):
    args = FioCommandBuilder().build("/dev/nvme2n1", "rand_read_4k", FioParameters(), str(tmp_path / "fio.json"), str(tmp_path / "run"))
    assert args[0] == "fio"
    assert "--ioengine=io_uring" in args and "--output-format=json+" in args
    assert "--filename=/dev/nvme2n1" in args and "--percentile_list=50:90:95:99:99.9:99.99" in args


@pytest.mark.parametrize("bad", ["nvme0n1", "/dev/nvme0", "/dev/nvme0n1p1", "/dev/nvme0n1;rm", "/tmp/disk"])
def test_illegal_device_path_rejected(bad):
    with pytest.raises(ValueError):
        validate_namespace_path(bad)


def test_numa_prefers_sys_block_path(monkeypatch):
    paths = []

    def fake_read(path, default=""):
        paths.append(str(path))
        return "1" if str(path) == "/sys/block/nvme2n1/device/numa_node" else default

    monkeypatch.setattr(DeviceService, "_read", staticmethod(fake_read))
    assert DeviceService()._read_numa_node("nvme2n1", "nvme2") == "1"
    assert paths == ["/sys/block/nvme2n1/device/numa_node"]


def test_numa_falls_back_to_controller_path(monkeypatch):
    def fake_read(path, default=""):
        return "2" if str(path) == "/sys/class/nvme/nvme2/device/numa_node" else default

    monkeypatch.setattr(DeviceService, "_read", staticmethod(fake_read))
    assert DeviceService()._read_numa_node("nvme2n1", "nvme2") == "2"


def test_system_disk_rejected():
    with pytest.raises(ValueError, match="系统盘"):
        SafetyService(FakeDevices(device(is_system_disk=True))).validate(request())


def test_mounted_write_rejected():
    with pytest.raises(ValueError, match="已挂载"):
        SafetyService(FakeDevices(device(mounted=True))).validate(request("rand_write_4k", destructive_confirmed=True, confirmation_device="/dev/nvme2n1"))


def test_destructive_confirmation_required():
    with pytest.raises(ValueError, match="手工输入"):
        SafetyService(FakeDevices(device())).validate(request("seq_write_128k"))


def test_smart_parser():
    parsed = parse_smart_json(json.dumps({"temperature": 308, "percent_used": 3, "media_errors": "2", "data_units_written": 100}))
    assert parsed == {"temperature": 308, "percentage_used": 3, "data_units_written": 100, "media_errors": 2}


def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200 and response.json()["version"] == "1.0.0"


def test_api_create_and_list(client):
    with patch("app.api.tests.SafetyService.validate", return_value=device()):
        created = client.post("/api/tests", json={"name": "read", "device": "/dev/nvme2n1", "test_type": "rand_read_4k"})
    assert created.status_code == 201
    assert client.get("/api/tests").json()[0]["name"] == "read"
