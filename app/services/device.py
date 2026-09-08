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
        proc = self._run(["lsblk", "-J", "-b", "-o", "NAME,PATH,TYPE,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINTS,PKNAME"])
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
            sys_block = Path("/sys/class/block") / name
            ctrl_name = Path(controller).name
            devices.append({
                "name": path, "namespace": path, "controller": controller,
                "model": (item.get("model") or "").strip(), "serial": (item.get("serial") or "").strip(),
                "firmware": self._read(Path("/sys/class/nvme") / ctrl_name / "firmware_rev"),
                "capacity_bytes": int(item.get("size") or 0),
                "pcie_address": self._read(Path("/sys/class/nvme") / ctrl_name / "address"),
                "numa_node": self._read(sys_block / "device" / "numa_node", "unknown"),
                "mounted": bool(mounts), "mountpoints": mounts,
                "has_partitions": bool(children),
                "has_filesystem": bool(item.get("fstype") or any(c.get("fstype") for c in children)),
                "in_use": bool(mounts), "is_system_disk": self._is_system_disk(path),
            })
        return devices

    @staticmethod
    def _read(path: Path, default: str = "") -> str:
        try:
            return path.read_text().strip()
        except OSError:
            return default

    def _is_system_disk(self, device: str) -> bool:
        proc = self._run(["findmnt", "-n", "-o", "SOURCE", "/"])
        source = proc.stdout.strip()
        return bool(source and (source == device or source.startswith(device + "p")))

    def get(self, device: str) -> dict[str, Any] | None:
        return next((d for d in self.scan() if d["name"] == device), None)


def validate_namespace_path(path: str) -> None:
    if not NAMESPACE_RE.fullmatch(path):
        raise ValueError("设备必须是精确的 NVMe Namespace 路径，例如 /dev/nvme2n1")

