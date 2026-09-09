from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.task import TestTask
from app.schemas.tasks import TestCreate, TestRead, TestStart
from app.services.device import validate_namespace_path
from app.services.fio import FioCommandBuilder, build_execution_plan, format_command_preview, parameters_for_phase
from app.services.parameters import visible_task_parameters
from app.services.safety import SafetyService
from app.services.smart import smart_delta
from app.services.task_manager import task_manager


router = APIRouter(prefix="/api/tests", tags=["tests"])


@router.post("", response_model=TestRead, status_code=201)
def create_test(payload: TestCreate, db: Session = Depends(get_db)):
    try:
        device_info = SafetyService().validate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    task = TestTask(name=payload.name, device=payload.device, test_type=payload.test_type,
                    parameters_json=payload.parameters.model_dump_json(exclude_none=True), device_info_json=json.dumps(device_info, ensure_ascii=False))
    db.add(task); db.commit(); db.refresh(task)
    return task


@router.post("/preview-command")
def preview_command(payload: TestCreate):
    try:
        validate_namespace_path(payload.device)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    parameters = payload.parameters
    builder = FioCommandBuilder()
    commands = []
    for phase, profile, queue_depth in build_execution_plan(payload.test_type, parameters):
        run_dir = settings.results_dir / "TASK_ID" / phase
        command_parameters = parameters_for_phase(parameters, phase)
        argv = builder.build(
            payload.device,
            profile,
            command_parameters,
            str(run_dir / "fio.json"),
            str(run_dir / "fio"),
            queue_depth,
        )
        formatted = format_command_preview(argv)
        commands.append({
            "phase": phase,
            "queue_depth": queue_depth,
            "argv": argv,
            "command": formatted["multiline_command"],
            "groups": formatted["groups"],
        })
    return {"commands": commands, "result_path_note": "TASK_ID 会在任务创建后替换为实际任务 ID"}


@router.get("", response_model=list[TestRead])
def list_tests(db: Session = Depends(get_db)):
    return list(db.scalars(select(TestTask).where(TestTask.deleted == 0).order_by(TestTask.created_at.desc())))


@router.get("/{test_id}")
def get_test(test_id: str, db: Session = Depends(get_db)):
    task = db.get(TestTask, test_id)
    if not task or task.deleted:
        raise HTTPException(404, "任务不存在")
    result = TestRead.model_validate(task).model_dump(mode="json")
    result["parameters"] = visible_task_parameters(task.test_type, task.parameters_json)
    result["result_summary"] = json.loads(task.result_summary_json) if task.result_summary_json else None
    result["queue_position"] = None
    if task.status == "queued":
        queued_ids = list(db.scalars(select(TestTask.id).where(
            TestTask.status == "queued",
            TestTask.deleted == 0,
        ).order_by(TestTask.created_at.asc(), TestTask.id.asc())))
        result["queue_position"] = queued_ids.index(task.id) + 1
    return result


@router.post("/{test_id}/start", response_model=TestRead)
def start_test(test_id: str, payload: TestStart = TestStart()):
    try:
        return task_manager.start(test_id, payload)
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{test_id}/stop")
def stop_test(test_id: str):
    try:
        return {"status": task_manager.stop(test_id)}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/{test_id}/smart-raw/{snapshot}")
def download_smart_raw(test_id: str, snapshot: str, db: Session = Depends(get_db)):
    if snapshot not in {"before", "after"}:
        raise HTTPException(404, "SMART Raw Data 快照不存在")
    task = db.get(TestTask, test_id)
    if not task or task.deleted:
        raise HTTPException(404, "任务不存在")
    if task.result_dir:
        raw_file = Path(task.result_dir) / f"smart_{snapshot}.bin"
        if raw_file.is_file():
            return FileResponse(raw_file, media_type="application/octet-stream", filename=f"smart_{snapshot}_{test_id}.bin")
    payload = task.smart_before_json if snapshot == "before" else task.smart_after_json
    try:
        raw_hex = json.loads(payload or "{}").get("raw_data", {}).get("hex")
        raw_bytes = bytes.fromhex(raw_hex) if raw_hex else None
    except (TypeError, ValueError, json.JSONDecodeError):
        raw_bytes = None
    if not raw_bytes:
        raise HTTPException(404, "该任务没有可下载的 SMART Raw Data")
    return Response(
        content=raw_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="smart_{snapshot}_{test_id}.bin"'},
    )


@router.get("/{test_id}/results")
def get_results(test_id: str, db: Session = Depends(get_db)):
    task = db.get(TestTask, test_id)
    if not task or task.deleted:
        raise HTTPException(404, "任务不存在")
    before = json.loads(task.smart_before_json) if task.smart_before_json else None
    after = json.loads(task.smart_after_json) if task.smart_after_json else None
    summary = json.loads(task.result_summary_json) if task.result_summary_json else None
    if summary is None and task.result_dir and Path(task.result_dir).is_dir():
        summary = {"runs": [], "timeseries": task_manager._collect_logs(Path(task.result_dir))}
    return {"status": task.status, "summary": summary,
            "smart_before": before, "smart_after": after, "smart_delta": smart_delta(before, after)}


@router.get("/{test_id}/logs")
def get_logs(test_id: str, db: Session = Depends(get_db)):
    task = db.get(TestTask, test_id)
    if not task or task.deleted:
        raise HTTPException(404, "任务不存在")
    files = {}
    if task.result_dir:
        base = Path(task.result_dir)
        if base.is_dir():
            for path in base.rglob("*.log"):
                files[str(path.relative_to(base))] = path.read_text(errors="replace")[-200_000:]
    return {"files": files, "error": task.error_message}


@router.delete("/{test_id}")
def delete_history(test_id: str, db: Session = Depends(get_db)):
    task = db.get(TestTask, test_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task.status in {"running", "queued"}:
        raise HTTPException(409, "运行中或排队中的任务不能删除")
    task.deleted = 1; db.commit()
    return {"deleted": True, "results_preserved": True}


@router.get("/processes/running")
def running_processes():
    return task_manager.running_processes()
