from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


NAMESPACE_RE = re.compile(r"^/dev/nvme\d+n\d+$")


class DeviceService:
    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)

    def scan(self) -> list[dict[str, Any]]:
        proc = self._run(["lsblk", "-J", "-b", "-o", "NAME,PATH,TYPE,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINTS,PKNAME,TRAN,ROTA,RO"])
        if proc.returncode:
            return []
        devices: list[dict[str, Any]] = []
        for item in json.loads(proc.stdout or "{}").get("blockdevices", []):
            path = item.get("path", "")
            if item.get("type") != "disk" or not NAMESPACE_RE.fullmatch(path):
                continue
            name = item["name"]
            controller = "/dev/" + re.sub(r"n\d+$", "", name)
            children = item.get("children") or []
            mounts = [m for m in (item.get("mountpoints") or []) if m]
            for child in children:
                mounts.extend(m for m in (child.get("mountpoints") or []) if m)
            ctrl_name = Path(controller).name
            has_partitions = bool(children)
            has_filesystem = bool(item.get("fstype") or any(c.get("fstype") for c in children))
            is_system_disk = self._is_system_disk(path) or any(m in {"/", "/boot", "/boot/efi"} for m in mounts)
            has_holders = self._has_holders(name)
            transport = (item.get("tran") or "").lower()
            controller_exists = (Path("/sys/class/nvme") / ctrl_name).exists()
            is_nvme = bool(NAMESPACE_RE.fullmatch(path)) and (transport == "nvme" or controller_exists)
            rotational = item.get("rota")
            if rotational is None:
                rotational = self._read(Path("/sys/block") / name / "queue" / "rotational", "unknown")
            is_ssd = rotational in (False, 0, "0")
            read_only = item.get("ro") in (True, 1, "1")
            device_info = {
                "name": path, "namespace": path, "controller": controller,
                "model": (item.get("model") or "").strip(), "serial": (item.get("serial") or "").strip(),
                "firmware": self._read(Path("/sys/class/nvme") / ctrl_name / "firmware_rev"),
                "capacity_bytes": int(item.get("size") or 0),
                "pcie_address": self._read(Path("/sys/class/nvme") / ctrl_name / "address"),
                "numa_node": self._read_numa_node(name, ctrl_name),
                "mounted": bool(mounts), "mountpoints": mounts,
                "has_partitions": has_partitions, "has_filesystem": has_filesystem,
                "in_use": bool(mounts) or has_holders, "is_system_disk": is_system_disk,
                "transport": transport or "unknown", "is_nvme": is_nvme, "is_ssd": is_ssd,
                "read_only": read_only,
            }
            reasons = []
            if not is_nvme:
                reasons.append("不是 NVMe 设备")
            if not is_ssd:
                reasons.append("不是非旋转 SSD")
            if is_system_disk:
                reasons.append("系统盘或启动盘")
            if mounts:
                reasons.append("设备或分区已挂载")
            if has_partitions:
                reasons.append("包含分区")
            if has_filesystem:
                reasons.append("包含文件系统")
            if has_holders:
                reasons.append("设备正被内核存储栈占用")
            if read_only:
                reasons.append("设备处于只读状态")
            device_info["test_eligible"] = not reasons
            device_info["ineligible_reasons"] = reasons
            devices.append(device_info)
        return devices

    @staticmethod
    def _read(path: Path, default: str = "") -> str:
        try:
            return path.read_text().strip()
        except OSError:
            return default

    def _read_numa_node(self, namespace: str, controller: str) -> str:
        """Read NUMA affinity across kernel/sysfs layouts.

        `/sys/block` is the canonical block-device view used by lsblk.  Some
        kernels expose the attribute only through the controller's PCI device,
        so keep both class and controller paths as safe read-only fallbacks.
        """
        candidates = (
            Path("/sys/block") / namespace / "device" / "numa_node",
            Path("/sys/class/block") / namespace / "device" / "numa_node",
            Path("/sys/class/nvme") / controller / "device" / "numa_node",
        )
        for path in candidates:
            value = self._read(path)
            if value != "":
                return value
        return "unknown"

    def _is_system_disk(self, device: str) -> bool:
        proc = self._run(["findmnt", "-n", "-o", "SOURCE", "/"])
        source = proc.stdout.strip()
        return bool(source and (source == device or source.startswith(device + "p")))

    @staticmethod
    def _has_holders(namespace: str) -> bool:
        try:
            return any((Path("/sys/block") / namespace / "holders").iterdir())
        except OSError:
            return False

    def get(self, device: str) -> dict[str, Any] | None:
        return next((d for d in self.scan() if d["name"] == device), None)


def validate_namespace_path(path: str) -> None:
    if not NAMESPACE_RE.fullmatch(path):
        raise ValueError("设备必须是精确的 NVMe Namespace 路径，例如 /dev/nvme2n1")
