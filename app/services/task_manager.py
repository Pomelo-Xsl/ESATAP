from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.task import TaskStatus, TestTask
from app.schemas.tasks import FioParameters, TestCreate, TestStart
from app.services.analyzer import parse_fio_file, parse_fio_log
from app.services.fio import FioCommandBuilder
from app.services.safety import SafetyService
from app.services.smart import SmartService


TERMINAL = {TaskStatus.completed.value, TaskStatus.failed.value, TaskStatus.stopped.value}


class TaskManager:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ssd-test")
        self.processes: dict[str, subprocess.Popen[str]] = {}
        self.stop_events: dict[str, threading.Event] = {}
        self.lock = threading.RLock()
        self.fio = FioCommandBuilder()
        self.safety = SafetyService()
        self.smart = SmartService()

    def start(self, test_id: str, confirmation: TestStart) -> TestTask:
        with self.lock, SessionLocal() as db:
            task = db.get(TestTask, test_id)
            if not task or task.deleted:
                raise ValueError("任务不存在")
            if task.status != TaskStatus.pending.value:
                raise ValueError("只有 pending 任务可以启动")
            params = FioParameters.model_validate_json(task.parameters_json)
            validation = TestCreate(name=task.name, device=task.device, test_type=task.test_type,
                                    parameters=params, destructive_confirmed=confirmation.destructive_confirmed,
                                    confirmation_device=confirmation.confirmation_device)
            self.safety.validate(validation)
            conflict = db.scalar(select(TestTask).where(TestTask.device == task.device, TestTask.status == TaskStatus.running.value))
            if conflict:
                raise ValueError("同一 SSD 同一时间只能运行一个测试任务")
            result_dir = settings.results_dir / task.id
            result_dir.mkdir(parents=True, exist_ok=False)
            task.status = TaskStatus.running.value
            task.progress = 0
            task.started_at = datetime.now(timezone.utc)
            task.result_dir = str(result_dir)
            db.commit(); db.refresh(task)
            event = threading.Event()
            self.stop_events[test_id] = event
            self.pool.submit(self._execute, test_id, event)
            return task

    def _save_smart(self, path: Path, device: str) -> dict[str, Any] | None:
        try:
            value = self.smart.collect(device)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            return value
        except Exception as exc:
            path.with_suffix(".error.log").write_text(str(exc), encoding="utf-8")
            return None

    def _execute(self, test_id: str, stop_event: threading.Event) -> None:
        with SessionLocal() as db:
            task = db.get(TestTask, test_id)
            if not task:
                return
            result_dir = Path(task.result_dir or "")
            params = FioParameters.model_validate_json(task.parameters_json)
            before = self._save_smart(result_dir / "smart_before.json", task.device)
            task.smart_before_json = json.dumps(before, ensure_ascii=False) if before else None
            db.commit()
            qds = params.queue_depths if task.test_type == "qd_scan" else [params.queue_depth]
            plan = []
            if params.precondition:
                plan.append(("precondition", "stress_seq_write", params.queue_depth))
            plan.extend((f"qd_{qd}" if len(qds) > 1 else "run", task.test_type, qd) for qd in qds)
            summaries = []
            commands = []
            started = time.monotonic()
            last_smart_sample = 0.0
            try:
                for index, (phase, profile, qd) in enumerate(plan):
                    if stop_event.is_set():
                        break
                    run_dir = result_dir / phase
                    run_dir.mkdir(parents=True, exist_ok=True)
                    output = run_dir / "fio.json"
                    command_params = params.model_copy(update={"size": "100%"}) if phase == "precondition" else params
                    command = self.fio.build(task.device, profile, command_params, str(output), str(run_dir / "fio"), qd)
                    commands.append(command)
                    (run_dir / "command.json").write_text(json.dumps(command, ensure_ascii=False, indent=2), encoding="utf-8")
                    with (run_dir / "stdout.log").open("w", encoding="utf-8") as stdout, (run_dir / "stderr.log").open("w", encoding="utf-8") as stderr:
                        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr, text=True, start_new_session=True)
                        with self.lock:
                            self.processes[test_id] = proc
                        task.pid = proc.pid; db.commit()
                        while proc.poll() is None:
                            if stop_event.wait(1):
                                self._terminate(proc)
                                break
                            elapsed = time.monotonic() - started
                            total = max(params.runtime_seconds * len(plan), 1)
                            task.progress = min(99.0, elapsed / total * 100)
                            db.commit()
                            if elapsed - last_smart_sample >= 30:
                                last_smart_sample = elapsed
                                try:
                                    sample = self.smart.collect(task.device)
                                    sample["timestamp"] = datetime.now(timezone.utc).isoformat()
                                    with (result_dir / "smart_timeseries.jsonl").open("a", encoding="utf-8") as smart_log:
                                        smart_log.write(json.dumps(sample, ensure_ascii=False) + "\n")
                                except Exception:
                                    pass
                        returncode = proc.wait()
                    if stop_event.is_set():
                        break
                    if returncode != 0:
                        raise RuntimeError(f"fio 退出码 {returncode}，请查看 stderr.log")
                    if not output.exists():
                        raise RuntimeError("fio 未生成 JSON 结果")
                    summary = parse_fio_file(output)
                    summary["queue_depth"] = qd
                    summary["phase"] = phase
                    summaries.append(summary)
                task.fio_command_json = json.dumps(commands, ensure_ascii=False)
                if stop_event.is_set():
                    task.status = TaskStatus.stopped.value
                    task.error_message = "任务已由用户停止"
                else:
                    result = {"runs": summaries, "timeseries": self._collect_logs(result_dir)}
                    (result_dir / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                    task.result_summary_json = json.dumps(result, ensure_ascii=False)
                    task.status = TaskStatus.completed.value
                    task.progress = 100
            except Exception as exc:
                task.status = TaskStatus.stopped.value if stop_event.is_set() else TaskStatus.failed.value
                task.error_message = str(exc)
            finally:
                after = self._save_smart(result_dir / "smart_after.json", task.device)
                task.smart_after_json = json.dumps(after, ensure_ascii=False) if after else None
                task.ended_at = datetime.now(timezone.utc)
                task.duration_seconds = round(time.monotonic() - started, 3)
                task.pid = None
                db.commit()
                with self.lock:
                    self.processes.pop(test_id, None)
                    self.stop_events.pop(test_id, None)

    @staticmethod
    def _collect_logs(result_dir: Path) -> dict[str, list[dict[str, float]]]:
        result: dict[str, list[dict[str, float]]] = {"iops": [], "bandwidth_kib_s": [], "latency_ns": [], "temperature_kelvin": []}
        patterns = {"iops": "*iops*.log", "bandwidth_kib_s": "*bw*.log", "latency_ns": "*lat*.log"}
        for key, pattern in patterns.items():
            for path in result_dir.rglob(pattern):
                result[key].extend(parse_fio_log(path))
            result[key].sort(key=lambda x: x["time_ms"])
        smart_log = result_dir / "smart_timeseries.jsonl"
        if smart_log.exists():
            for line in smart_log.read_text(errors="replace").splitlines():
                try:
                    sample = json.loads(line)
                    result["temperature_kelvin"].append({"timestamp": sample.get("timestamp", ""), "value": float(sample["temperature"])})
                except (ValueError, KeyError, json.JSONDecodeError):
                    continue
        return result

    @staticmethod
    def _terminate(proc: subprocess.Popen[str]) -> None:
        if proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass

    def stop(self, test_id: str) -> None:
        with self.lock:
            proc = self.processes.get(test_id)
            event = self.stop_events.get(test_id)
            if not proc or not event:
                raise ValueError("任务未在当前服务进程中运行，拒绝终止未知进程")
            event.set()
            self._terminate(proc)

    def running_processes(self) -> list[dict[str, Any]]:
        with self.lock:
            return [{"test_id": key, "pid": proc.pid, "running": proc.poll() is None} for key, proc in self.processes.items()]


task_manager = TaskManager()
