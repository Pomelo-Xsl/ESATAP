from __future__ import annotations

import json
import subprocess
from typing import Any


SMART_KEYS = {
    "critical_warning": "critical_warning", "temperature": "temperature",
    "avail_spare": "available_spare", "available_spare": "available_spare",
    "percent_used": "percentage_used", "percentage_used": "percentage_used",
    "data_units_read": "data_units_read", "data_units_written": "data_units_written",
    "host_read_commands": "host_read_commands", "host_write_commands": "host_write_commands",
    "controller_busy_time": "controller_busy_time", "power_cycles": "power_cycles",
    "power_on_hours": "power_on_hours", "unsafe_shutdowns": "unsafe_shutdowns",
    "media_errors": "media_errors", "num_err_log_entries": "error_information_log_entries",
}


def _number(value: Any) -> int | float | str | None:
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.replace(",", "").split()[0] if value.strip() else ""
        try:
            return float(cleaned) if "." in cleaned else int(cleaned, 0)
        except ValueError:
            return value
    return value


def parse_smart_json(payload: str | dict[str, Any]) -> dict[str, Any]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    return {target: _number(data.get(source)) for source, target in SMART_KEYS.items() if source in data}


def smart_delta(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    result = {}
    for key in set(before or {}) | set(after or {}):
        a, b = (before or {}).get(key), (after or {}).get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            result[key] = b - a
    if "data_units_written" in result:
        result["written_bytes_approx"] = result["data_units_written"] * 512000
    return result


class SmartService:
    def collect(self, device: str) -> dict[str, Any]:
        proc = subprocess.run(["nvme", "smart-log", "-o", "json", device], capture_output=True, text=True, timeout=15, check=False)
        if proc.returncode:
            raise RuntimeError(proc.stderr.strip() or "nvme smart-log 执行失败")
        return parse_smart_json(proc.stdout)

