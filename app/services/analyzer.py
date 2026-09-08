from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _latency_section(io: dict[str, Any]) -> tuple[dict[str, Any], float]:
    for key, factor in (("clat_ns", 0.001), ("lat_ns", 0.001), ("clat_us", 1.0), ("lat_us", 1.0), ("clat_ms", 1000.0), ("lat_ms", 1000.0)):
        if key in io:
            return io[key] or {}, factor
    return {}, 1.0


def _percentile(section: dict[str, Any], target: str) -> Any:
    values = section.get("percentile") or {}
    candidates = [target, f"{float(target):.6f}"]
    for key in candidates:
        if key in values:
            return values[key]
    return None


def parse_fio_json(payload: str | dict[str, Any]) -> dict[str, Any]:
    data = json.loads(payload) if isinstance(payload, str) else payload
    directions = {}
    total_errors = 0
    for direction in ("read", "write"):
        ios = [job.get(direction, {}) for job in data.get("jobs", [])]
        active = [io for io in ios if (io.get("io_bytes", 0) or io.get("iops", 0))]
        if not active:
            continue
        iops = sum(float(io.get("iops", 0)) for io in active)
        bw_bytes = sum(float(io.get("bw_bytes", float(io.get("bw", 0)) * 1024)) for io in active)
        total_bytes = sum(int(io.get("io_bytes", 0)) for io in active)
        weights = [max(float(io.get("total_ios", 0)), 1.0) for io in active]
        lat_entries = [_latency_section(io) for io in active]

        def weighted(field: str) -> float:
            values = [float(section.get(field, 0)) * factor for section, factor in lat_entries]
            return sum(v * w for v, w in zip(values, weights)) / sum(weights)

        percentiles = {}
        for p in ("50", "90", "95", "99", "99.9", "99.99"):
            vals = []
            for section, factor in lat_entries:
                val = _percentile(section, p)
                if val is not None:
                    vals.append(float(val) * factor)
            percentiles[f"p{p}"] = max(vals) if vals else None
        directions[direction] = {
            "iops": round(iops, 2), "bandwidth_bytes_per_sec": round(bw_bytes, 2),
            "bandwidth_mb_per_sec": round(bw_bytes / 1_000_000, 2), "total_bytes": total_bytes,
            "latency_us": {"mean": round(weighted("mean"), 3),
                           "min": round(min(float(s.get("min", 0)) * f for s, f in lat_entries), 3),
                           "max": round(max(float(s.get("max", 0)) * f for s, f in lat_entries), 3),
                           **percentiles},
        }
    for job in data.get("jobs", []):
        total_errors += int(job.get("error", 0) or 0)
        total_errors += int(job.get("read", {}).get("errors", 0) or 0)
        total_errors += int(job.get("write", {}).get("errors", 0) or 0)
    return {"fio_version": data.get("fio version") or data.get("fio_version"), "directions": directions,
            "total_read_bytes": directions.get("read", {}).get("total_bytes", 0),
            "total_write_bytes": directions.get("write", {}).get("total_bytes", 0),
            "error_count": total_errors}


def parse_fio_file(path: Path) -> dict[str, Any]:
    return parse_fio_json(path.read_text(encoding="utf-8"))


def parse_fio_log(path: Path) -> list[dict[str, float]]:
    points = []
    if not path.exists():
        return points
    for line in path.read_text(errors="replace").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            try:
                points.append({"time_ms": float(parts[0]), "value": float(parts[1])})
            except ValueError:
                continue
    return points

