import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.models.task import TaskStatus
from app.services.analyzer import parse_fio_json
from app.services.smart import smart_delta
from app.services.task_manager import TaskManager


SAMPLE = {
    "fio version": "fio-3.36",
    "jobs": [{
        "error": 0,
        "read": {"iops": 1000.5, "bw_bytes": 4096000, "io_bytes": 8192000, "total_ios": 2000,
                 "clat_ns": {"min": 1000, "max": 100000, "mean": 5000,
                             "percentile": {"50.000000": 4096, "90.000000": 8192, "95.000000": 10000,
                                            "99.000000": 20000, "99.900000": 40000, "99.990000": 80000}}},
        "write": {"iops": 0, "io_bytes": 0}
    }]
}


def test_fio_json_parser_units_and_percentiles():
    result = parse_fio_json(SAMPLE)
    read = result["directions"]["read"]
    assert read["iops"] == 1000.5
    assert read["bandwidth_mb_per_sec"] == 4.1
    assert read["latency_us"]["mean"] == 5
    assert read["latency_us"]["p99.9"] == 40
    assert result["total_read_bytes"] == 8192000 and result["error_count"] == 0


def test_smart_delta_and_written_bytes():
    delta = smart_delta({"temperature": 300, "data_units_written": 10}, {"temperature": 305, "data_units_written": 12})
    assert delta["temperature"] == 5 and delta["written_bytes_approx"] == 1_024_000


def test_task_status_values():
    assert {s.value for s in TaskStatus} == {"pending", "running", "completed", "failed", "stopped"}


def test_stop_only_registered_process():
    manager = TaskManager()
    with pytest.raises(ValueError, match="拒绝终止"):
        manager.stop("unknown")

    proc = Mock(pid=4321)
    proc.poll.return_value = None
    event = manager.stop_events["known"] = __import__("threading").Event()
    manager.processes["known"] = proc
    with patch.object(manager, "_terminate") as terminate:
        manager.stop("known")
    assert event.is_set()
    terminate.assert_called_once_with(proc)


def test_results_api_missing(client):
    assert client.get("/api/tests/not-found/results").status_code == 404
