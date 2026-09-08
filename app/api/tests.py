from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.task import TestTask
from app.schemas.tasks import TestCreate, TestRead, TestStart
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
                    parameters_json=payload.parameters.model_dump_json(), device_info_json=json.dumps(device_info, ensure_ascii=False))
    db.add(task); db.commit(); db.refresh(task)
    return task


@router.get("", response_model=list[TestRead])
def list_tests(db: Session = Depends(get_db)):
    return list(db.scalars(select(TestTask).where(TestTask.deleted == 0).order_by(TestTask.created_at.desc())))


@router.get("/{test_id}")
def get_test(test_id: str, db: Session = Depends(get_db)):
    task = db.get(TestTask, test_id)
    if not task or task.deleted:
        raise HTTPException(404, "任务不存在")
    result = TestRead.model_validate(task).model_dump(mode="json")
    result["parameters"] = json.loads(task.parameters_json)
    result["result_summary"] = json.loads(task.result_summary_json) if task.result_summary_json else None
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
        task_manager.stop(test_id)
        return {"status": "stopping"}
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


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
    if task.status == "running":
        raise HTTPException(409, "运行中的任务不能删除")
    task.deleted = 1; db.commit()
    return {"deleted": True, "results_preserved": True}


@router.get("/processes/running")
def running_processes():
    return task_manager.running_processes()
