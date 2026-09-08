import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.core.database import SessionLocal
from app.models.task import TaskStatus, TestTask as TaskModel
from app.schemas.tasks import TestStart as StartSchema
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
    assert {s.value for s in TaskStatus} == {"pending", "queued", "running", "completed", "failed", "stopped"}


def test_start_queues_when_same_device_is_running():
    manager = TaskManager()
    manager.pool = Mock()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        running = TaskModel(name="running", device="/dev/nvme2n1", test_type="rand_read_4k",
                           parameters_json="{}", status="running", started_at=now)
        waiting = TaskModel(name="waiting", device="/dev/nvme2n1", test_type="rand_read_4k",
                           parameters_json="{}")
        db.add_all([running, waiting]); db.commit(); waiting_id = waiting.id

    with patch.object(manager.safety, "validate", return_value={}):
        result = manager.start(waiting_id, StartSchema())

    assert result.status == "queued"
    manager.pool.submit.assert_not_called()


def test_dispatch_starts_oldest_queued_task(tmp_path):
    manager = TaskManager()
    manager.pool = Mock()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        first = TaskModel(name="first", device="/dev/nvme2n1", test_type="rand_read_4k",
                         parameters_json="{}", status="queued", created_at=now)
        second = TaskModel(name="second", device="/dev/nvme2n1", test_type="rand_read_4k",
                          parameters_json="{}", status="queued", created_at=now + timedelta(seconds=1))
        db.add_all([first, second]); db.commit(); first_id, second_id = first.id, second.id

    with patch("app.services.task_manager.settings", SimpleNamespace(results_dir=tmp_path)), \
         patch.object(manager.safety, "validate", return_value={}):
        manager._dispatch_next("/dev/nvme2n1")

    with SessionLocal() as db:
        assert db.get(TaskModel, first_id).status == "running"
        assert db.get(TaskModel, second_id).status == "queued"
    manager.pool.submit.assert_called_once()


def test_dispatch_skips_queue_item_that_fails_fresh_safety_check(tmp_path):
    manager = TaskManager()
    manager.pool = Mock()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        unsafe = TaskModel(name="unsafe", device="/dev/nvme2n1", test_type="rand_read_4k",
                           parameters_json="{}", status="queued", created_at=now)
        safe = TaskModel(name="safe", device="/dev/nvme2n1", test_type="rand_read_4k",
                         parameters_json="{}", status="queued", created_at=now + timedelta(seconds=1))
        db.add_all([unsafe, safe]); db.commit(); unsafe_id, safe_id = unsafe.id, safe.id

    with patch("app.services.task_manager.settings", SimpleNamespace(results_dir=tmp_path)), \
         patch.object(manager.safety, "validate", side_effect=[ValueError("设备已挂载"), {}]):
        manager._dispatch_next("/dev/nvme2n1")

    with SessionLocal() as db:
        rejected = db.get(TaskModel, unsafe_id)
        assert rejected.status == "failed"
        assert "设备已挂载" in rejected.error_message
        assert db.get(TaskModel, safe_id).status == "running"
    manager.pool.submit.assert_called_once()


def test_stop_cancels_queued_task():
    manager = TaskManager()
    manager.pool = Mock()
    with SessionLocal() as db:
        task = TaskModel(name="queued", device="/dev/nvme2n1", test_type="rand_read_4k",
                        parameters_json="{}", status="queued")
        blocker = TaskModel(name="running", device="/dev/nvme2n1", test_type="rand_read_4k",
                           parameters_json="{}", status="running")
        db.add_all([task, blocker]); db.commit(); task_id = task.id

    assert manager.stop(task_id) == "stopped"
    with SessionLocal() as db:
        assert db.get(TaskModel, task_id).status == "stopped"
        assert "取消" in db.get(TaskModel, task_id).error_message


def test_queued_task_api_reports_fifo_position(client):
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        first = TaskModel(name="first", device="/dev/nvme2n1", test_type="rand_read_4k",
                         parameters_json="{}", status="queued", created_at=now)
        second = TaskModel(name="second", device="/dev/nvme2n1", test_type="rand_read_4k",
                          parameters_json="{}", status="queued", created_at=now + timedelta(seconds=1))
        db.add_all([first, second]); db.commit(); second_id = second.id

    payload = client.get(f"/api/tests/{second_id}").json()
    assert payload["status"] == "queued"
    assert payload["queue_position"] == 2


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
