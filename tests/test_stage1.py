import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.schemas.tasks import FioParameters, TestCreate as CreateSchema
from app.services.device import DeviceService, validate_namespace_path
from app.services.fio import OPTION_MAP, FioCommandBuilder, is_destructive
from app.services.safety import SafetyService
from app.services.smart import SmartService, parse_smart_json, parse_smart_raw


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


def test_fio_command_includes_validated_advanced_parameters(tmp_path):
    params = FioParameters(
        io_engine="libaio", rw="randrw", block_size_split="4k/70:64k/30", direct=False,
        iodepth_batch=8, rwmixread=80, random_distribution="zipf:1.2", rate_iops=50000,
        latency_target_us=250, verify="crc32c", cpus_allowed="0-3,8", numa_mem_policy="bind:1",
        log_hist_msec=1000, end_fsync=True,
    )
    args = FioCommandBuilder().build("/dev/nvme2n1", "rand_read_4k", params,
                                     str(tmp_path / "fio.json"), str(tmp_path / "run"))
    assert "--ioengine=libaio" in args
    assert "--rw=randrw" in args and "--bssplit=4k/70:64k/30" in args
    assert "--direct=0" in args and "--iodepth_batch=8" in args
    assert "--rwmixread=80" in args and "--random_distribution=zipf:1.2" in args
    assert "--rate_iops=50000" in args and "--latency_target=250" in args
    assert "--verify=crc32c" in args and "--cpus_allowed=0-3,8" in args
    assert "--numa_mem_policy=bind:1" in args and "--log_hist_msec=1000" in args
    assert "--end_fsync=1" in args


def test_fio_command_can_be_wrapped_with_numactl(tmp_path):
    params = FioParameters(numactl_cpu_nodes="0", numactl_mem_nodes="0-1")
    args = FioCommandBuilder().build(
        "/dev/nvme2n1", "rand_read_4k", params,
        str(tmp_path / "fio.json"), str(tmp_path / "run"),
    )
    assert args[:4] == ["numactl", "--cpunodebind=0", "--membind=0-1", "fio"]
    assert "--filename=/dev/nvme2n1" in args


def test_numactl_node_binding_rejects_shell_or_option_injection():
    with pytest.raises(ValueError, match="numactl 节点格式无效"):
        FioParameters(numactl_cpu_nodes="0;touch")
    with pytest.raises(ValueError, match="numactl 节点格式无效"):
        FioParameters(numactl_mem_nodes="--all")


def test_every_validated_fio_parameter_is_mapped_to_command_generation():
    core_or_internal = {
        "block_size", "block_size_range", "block_size_split", "queue_depth", "queue_depths",
        "num_jobs", "runtime_seconds", "size", "precondition", "io_engine", "rw", "direct",
        "time_based", "group_reporting", "log_avg_msec", "latency_percentiles", "percentile_list",
        "numactl_cpu_nodes", "numactl_mem_nodes",
    }
    assert set(FioParameters.model_fields) == set(OPTION_MAP) | core_or_internal


def test_unknown_or_unsafe_fio_parameter_is_rejected():
    with pytest.raises(ValueError, match="extra_forbidden"):
        FioParameters.model_validate({"exec_prerun": "touch /tmp/unsafe"})


def test_mutually_exclusive_block_size_modes_are_rejected():
    with pytest.raises(ValueError, match="只能选择一种"):
        FioParameters(block_size="4k", block_size_range="4k-128k")


def test_rw_override_and_trim_are_classified_as_destructive():
    assert is_destructive("rand_read_4k", FioParameters(rw="randwrite"))
    assert is_destructive("rand_read_4k", FioParameters(trim_percentage=10))


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


def test_mounted_read_test_is_also_rejected():
    with pytest.raises(ValueError, match="已挂载"):
        SafetyService(FakeDevices(device(mounted=True))).validate(request("rand_read_4k"))


def test_non_nvme_device_is_rejected():
    with pytest.raises(ValueError, match="NVMe Namespace"):
        SafetyService(FakeDevices(device(is_nvme=False))).validate(request())


def test_rotational_or_non_ssd_device_is_rejected():
    with pytest.raises(ValueError, match="非旋转 NVMe SSD"):
        SafetyService(FakeDevices(device(is_ssd=False))).validate(request())


def test_partitioned_device_is_rejected_for_all_tests():
    with pytest.raises(ValueError, match="分区或文件系统"):
        SafetyService(FakeDevices(device(has_partitions=True))).validate(request("rand_read_4k"))


def test_device_in_use_is_rejected():
    with pytest.raises(ValueError, match="系统占用"):
        SafetyService(FakeDevices(device(in_use=True))).validate(request())


def test_destructive_confirmation_required():
    with pytest.raises(ValueError, match="手工输入"):
        SafetyService(FakeDevices(device())).validate(request("seq_write_128k"))


def test_read_profile_with_write_override_requires_confirmation():
    value = CreateSchema(name="override", device="/dev/nvme2n1", test_type="rand_read_4k",
                         parameters={"rw": "write"})
    with pytest.raises(ValueError, match="手工输入"):
        SafetyService(FakeDevices(device())).validate(value)


def test_smart_parser():
    parsed = parse_smart_json(json.dumps({"temperature": 308, "percent_used": 3, "media_errors": "2", "data_units_written": 100}))
    assert parsed == {"temperature": 308, "percentage_used": 3, "data_units_written": 100, "media_errors": 2}


def test_smart_raw_parser_uses_documented_byte_offsets_and_little_endian():
    raw = bytearray(512)
    raw[0] = 0b00000101
    raw[1:3] = (311).to_bytes(2, "little")
    raw[3] = 99
    raw[32:48] = (12345678901234567890).to_bytes(16, "little")
    raw[200:202] = (315).to_bytes(2, "little")
    raw[214:216] = (322).to_bytes(2, "little")
    raw[216:220] = (7).to_bytes(4, "little")
    raw[232:240] = (987654321).to_bytes(8, "little")
    raw[240:244] = (456).to_bytes(4, "little")

    parsed = parse_smart_raw(bytes(raw))
    fields = {field["key"]: field for field in parsed["fields"]}
    assert parsed["length_bytes"] == 512 and len(parsed["hex"]) == 1024
    assert fields["critical_warning"]["value"] == 5
    assert len(fields["critical_warning"]["active_warnings"]) == 2
    assert fields["composite_temperature"]["value"] == 311
    assert fields["data_units_read"]["value"] == 12345678901234567890
    assert fields["temperature_sensor_1"]["value"] == 315
    assert fields["temperature_sensor_8"]["value"] == 322
    assert fields["thermal_management_t1_transition_count"]["value"] == 7
    assert fields["operational_lifetime_energy_consumed"]["value"] == 987654321
    assert fields["interval_power_measurement"]["value"] == 456
    assert fields["reserved_244_511"]["byte_field"] == "511:244"
    assert fields["reserved_244_511"]["value"] is None


def test_smart_raw_parser_rejects_short_payload():
    with pytest.raises(ValueError, match="长度不足"):
        parse_smart_raw(bytes(511))


def test_smart_service_collects_json_and_raw_binary():
    json_proc = SimpleNamespace(returncode=0, stdout='{"temperature":311,"vendor_field":42}', stderr="")
    raw_proc = SimpleNamespace(returncode=0, stdout=bytes(512), stderr=b"")
    with patch("app.services.smart.subprocess.run", side_effect=[json_proc, raw_proc]) as run:
        result = SmartService().collect("/dev/nvme2n1")
    assert result["temperature"] == 311
    assert result["raw_json"]["vendor_field"] == 42
    assert result["raw_data"]["available"] is True
    assert run.call_args_list[1].args[0] == ["nvme", "smart-log", "/dev/nvme2n1", "--raw-binary"]


def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200 and response.json()["version"] == "1.0.0"


def test_api_create_and_list(client):
    with patch("app.api.tests.SafetyService.validate", return_value=device()):
        created = client.post("/api/tests", json={"name": "read", "device": "/dev/nvme2n1", "test_type": "rand_read_4k"})
    assert created.status_code == 201
    listed = client.get("/api/tests").json()[0]
    assert listed["name"] == "read"
    assert listed["numactl_cpu_nodes"] is None
    assert listed["numactl_mem_nodes"] is None


def test_task_list_exposes_saved_numactl_bindings(client):
    with patch("app.api.tests.SafetyService.validate", return_value=device()):
        created = client.post("/api/tests", json={
            "name": "numa-bound",
            "device": "/dev/nvme2n1",
            "test_type": "rand_read_4k",
            "parameters": {"numactl_cpu_nodes": "0", "numactl_mem_nodes": "0-1"},
        })
    assert created.status_code == 201
    listed = client.get("/api/tests").json()[0]
    assert listed["numactl_cpu_nodes"] == "0"
    assert listed["numactl_mem_nodes"] == "0-1"


def test_api_persists_advanced_fio_parameters(client):
    payload = {
        "name": "advanced",
        "device": "/dev/nvme2n1",
        "test_type": "rand_read_4k",
        "parameters": {
            "io_engine": "libaio", "block_size_split": "4k/80:64k/20", "queue_depth": 64,
            "random_distribution": "zipf:1.2", "rate_iops": 100000, "steadystate": "iops_slope:0.1%",
            "cpus_allowed": "0-3", "log_hist_msec": 1000,
        },
    }
    with patch("app.api.tests.SafetyService.validate", return_value=device()):
        created = client.post("/api/tests", json=payload)
    assert created.status_code == 201
    parameters = client.get(f"/api/tests/{created.json()['id']}").json()["parameters"]
    assert parameters["io_engine"] == "libaio"
    assert parameters["block_size_split"] == "4k/80:64k/20"
    assert parameters["steadystate"] == "iops_slope:0.1%"


def test_api_rejects_non_whitelisted_fio_parameter(client):
    response = client.post("/api/tests", json={
        "name": "unsafe", "device": "/dev/nvme2n1", "test_type": "rand_read_4k",
        "parameters": {"filename": "/dev/nvme0n1"},
    })
    assert response.status_code == 422


def test_command_preview_uses_real_builder_and_includes_managed_paths(client):
    response = client.post("/api/tests/preview-command", json={
        "name": "preview", "device": "/dev/nvme2n1", "test_type": "rand_read_4k",
        "parameters": {"queue_depth": 64, "io_engine": "libaio", "rate_iops": 50000},
    })
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["commands"]) == 1
    command = payload["commands"][0]["command"]
    assert "--filename=/dev/nvme2n1" in command
    assert "--ioengine=libaio" in command and "--iodepth=64" in command
    assert "--rate_iops=50000" in command
    assert "TASK_ID" in command and "--output=" in command and "--write_iops_log=" in command
    assert command.startswith("fio \\\n  --name=rand_read_4k")
    assert [group["label"] for group in payload["commands"][0]["groups"]] == [
        "任务与目标", "I/O 模式", "队列与并发", "运行控制", "负载与速率", "统计与输出",
    ]


def test_command_preview_shows_numactl_wrapper_before_fio(client):
    response = client.post("/api/tests/preview-command", json={
        "name": "numa preview", "device": "/dev/nvme2n1", "test_type": "rand_read_4k",
        "parameters": {"numactl_cpu_nodes": "0", "numactl_mem_nodes": "0"},
    })
    assert response.status_code == 200
    command = response.json()["commands"][0]
    assert command["argv"][:4] == ["numactl", "--cpunodebind=0", "--membind=0", "fio"]
    assert command["command"].splitlines()[:4] == [
        "numactl \\", "  --cpunodebind=0 \\", "  --membind=0 \\", "  fio \\",
    ]
    assert command["groups"][0] == {
        "label": "NUMA 进程绑定",
        "arguments": ["--cpunodebind=0", "--membind=0", "fio"],
    }


def test_qd_command_preview_lists_each_selected_depth(client):
    response = client.post("/api/tests/preview-command", json={
        "name": "qd preview", "device": "/dev/nvme2n1", "test_type": "qd_scan",
        "parameters": {"queue_depths": [1, 8, 64]},
    })
    commands = response.json()["commands"]
    assert [item["queue_depth"] for item in commands] == [1, 8, 64]
    assert [item["phase"] for item in commands] == ["qd_1", "qd_8", "qd_64"]


def test_command_preview_includes_destructive_precondition_as_separate_command(client):
    response = client.post("/api/tests/preview-command", json={
        "name": "precondition preview", "device": "/dev/nvme2n1", "test_type": "rand_read_4k",
        "parameters": {"precondition": True, "size": "10GiB", "rw": "randread"},
    })
    commands = response.json()["commands"]
    assert [item["phase"] for item in commands] == ["precondition", "run"]
    assert "--rw=write" in commands[0]["command"] and "--size=100%" in commands[0]["command"]
    assert "--rw=randread" in commands[1]["command"] and "--size=10GiB" in commands[1]["command"]
