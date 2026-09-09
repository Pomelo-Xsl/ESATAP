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

RAW_SMART_FIELDS = [
    (0, 1, "critical_warning", "Critical Warning", "关键告警位图，每个 bit 表示一种严重状态", None),
    (1, 2, "composite_temperature", "Composite Temperature", "当前综合温度", "K"),
    (3, 1, "available_spare", "Available Spare", "当前剩余备用空间百分比", "%"),
    (4, 1, "available_spare_threshold", "Available Spare Threshold", "备用空间告警阈值", "%"),
    (5, 1, "percentage_used", "Percentage Used", "SSD 预计寿命已经消耗的百分比", "%"),
    (6, 1, "endurance_group_critical_warning_summary", "Endurance Group Critical Warning Summary", "Endurance Group 的关键告警汇总", None),
    (7, 25, "reserved_7_31", "Reserved", "保留字段", None),
    (32, 16, "data_units_read", "Data Units Read", "Host 从 SSD 读取的数据总量", None),
    (48, 16, "data_units_written", "Data Units Written", "Host 写入 SSD 的数据总量", None),
    (64, 16, "host_read_commands", "Host Read Commands", "Host 发出的 Read Command 总数量", None),
    (80, 16, "host_write_commands", "Host Write Commands", "Host 发出的 Write Command 总数量", None),
    (96, 16, "controller_busy_time", "Controller Busy Time", "Controller 忙碌累计时间", "min"),
    (112, 16, "power_cycles", "Power Cycles", "设备上电次数", None),
    (128, 16, "power_on_hours", "Power On Hours", "累计上电小时数", "h"),
    (144, 16, "unsafe_shutdowns", "Unsafe Shutdowns / Unexpected Power Losses", "非正常掉电次数", None),
    (160, 16, "media_errors", "Media and Data Integrity Errors", "介质或数据完整性错误次数", None),
    (176, 16, "error_information_log_entries", "Number of Error Information Log Entries", "Error Log 中累计错误条目数量", None),
    (192, 4, "warning_composite_temperature_time", "Warning Composite Temperature Time", "温度达到 Warning Threshold 的累计时间", "min"),
    (196, 4, "critical_composite_temperature_time", "Critical Composite Temperature Time", "温度达到 Critical Threshold 的累计时间", "min"),
    *[(200 + index * 2, 2, f"temperature_sensor_{index + 1}", f"Temperature Sensor {index + 1}", f"温度传感器 {index + 1}", "K") for index in range(8)],
    (216, 4, "thermal_management_t1_transition_count", "Thermal Management T1 Transition Count", "进入温控状态 1 的次数", None),
    (220, 4, "thermal_management_t2_transition_count", "Thermal Management T2 Transition Count", "进入温控状态 2 的次数", None),
    (224, 4, "total_time_for_tmt1", "Total Time For TMT1", "处于温控状态 1 的累计时间", "s"),
    (228, 4, "total_time_for_tmt2", "Total Time For TMT2", "处于温控状态 2 的累计时间", "s"),
    (232, 8, "operational_lifetime_energy_consumed", "Operational Lifetime Energy Consumed", "生命周期累计能耗", None),
    (240, 4, "interval_power_measurement", "Interval Power Measurement", "区间功耗测量", None),
    (244, 268, "reserved_244_511", "Reserved", "保留字段", None),
]

CRITICAL_WARNING_BITS = {
    0: "Available Spare below threshold",
    1: "Temperature threshold exceeded",
    2: "NVM subsystem reliability degraded",
    3: "Media placed in read-only mode",
    4: "Volatile memory backup failed",
    5: "Persistent memory region read-only or unreliable",
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


def _hex_dump(payload: bytes) -> str:
    return "\n".join(
        f"{offset:04x}: " + " ".join(f"{byte:02x}" for byte in payload[offset:offset + 16])
        for offset in range(0, len(payload), 16)
    )


def parse_smart_raw(payload: bytes) -> dict[str, Any]:
    if len(payload) < 512:
        raise ValueError(f"NVMe SMART Raw Data 长度不足：期望 512 bytes，实际 {len(payload)} bytes")
    raw = payload[:512]
    fields = []
    for offset, length, key, name, description, unit in RAW_SMART_FIELDS:
        chunk = raw[offset:offset + length]
        reserved = key.startswith("reserved_")
        field = {
            "byte_field": str(offset) if length == 1 else f"{offset + length - 1}:{offset}",
            "offset": offset,
            "length": length,
            "key": key,
            "name": name,
            "description": description,
            "hex": chunk.hex(" "),
            "value": None if reserved else int.from_bytes(chunk, byteorder="little", signed=False),
            "unit": unit,
        }
        if key == "critical_warning":
            field["active_warnings"] = [label for bit, label in CRITICAL_WARNING_BITS.items() if chunk[0] & (1 << bit)]
        fields.append(field)
    return {
        "available": True,
        "length_bytes": len(raw),
        "byte_order": "little-endian",
        "hex": raw.hex(),
        "hex_dump": _hex_dump(raw),
        "fields": fields,
    }


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
        raw_json = json.loads(proc.stdout)
        result = parse_smart_json(raw_json)
        result["raw_json"] = raw_json
        raw_proc = subprocess.run(["nvme", "smart-log", device, "--raw-binary"], capture_output=True, timeout=15, check=False)
        if raw_proc.returncode:
            error = raw_proc.stderr.decode(errors="replace").strip() if isinstance(raw_proc.stderr, bytes) else str(raw_proc.stderr).strip()
            result["raw_data"] = {"available": False, "error": error or "nvme smart-log --raw-binary 执行失败"}
        else:
            try:
                result["raw_data"] = parse_smart_raw(raw_proc.stdout)
            except ValueError as exc:
                result["raw_data"] = {"available": False, "error": str(exc)}
        return result
