from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.core.database import get_db
from app.models.task import TestTask
from app.services.environment import environment_info
from app.services.parameters import visible_task_parameters
from app.services.smart import smart_delta


router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    tasks = list(db.scalars(select(TestTask).where(TestTask.deleted == 0).order_by(TestTask.created_at.desc()).limit(8)))
    return templates.TemplateResponse(request, "index.html", {"tasks": tasks,
        "task_count": db.scalar(select(func.count()).select_from(TestTask).where(TestTask.deleted == 0)) or 0,
        "running_count": db.scalar(select(func.count()).select_from(TestTask).where(TestTask.status == "running")) or 0})


@router.get("/devices", response_class=HTMLResponse)
def devices_page(request: Request):
    return templates.TemplateResponse(request, "devices.html")


@router.get("/tests/new", response_class=HTMLResponse)
def create_page(request: Request):
    return templates.TemplateResponse(request, "create_test.html")


@router.get("/tasks", response_class=HTMLResponse)
def tasks_page(request: Request):
    return templates.TemplateResponse(request, "tasks.html")


@router.get("/processes", response_class=HTMLResponse)
def processes_page(request: Request):
    return templates.TemplateResponse(request, "processes.html")


def _task_or_404(db: Session, test_id: str) -> TestTask:
    task = db.get(TestTask, test_id)
    if not task or task.deleted:
        raise HTTPException(404, "任务不存在")
    return task


@router.get("/tasks/{test_id}", response_class=HTMLResponse)
def task_detail(request: Request, test_id: str, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "task_detail.html", {"task": _task_or_404(db, test_id)})


@router.get("/tasks/{test_id}/live", response_class=HTMLResponse)
def task_live(request: Request, test_id: str, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "task_live.html", {"task": _task_or_404(db, test_id)})


@router.get("/tasks/{test_id}/analysis", response_class=HTMLResponse)
def task_analysis(request: Request, test_id: str, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "analysis.html", {"task": _task_or_404(db, test_id)})


@router.get("/tasks/{test_id}/report", response_class=HTMLResponse)
def task_report_page(request: Request, test_id: str, db: Session = Depends(get_db)):
    return _render_report(request, _task_or_404(db, test_id))


@router.get("/api/tests/{test_id}/report", response_class=HTMLResponse)
def task_report(request: Request, test_id: str, db: Session = Depends(get_db)):
    return _render_report(request, _task_or_404(db, test_id))


def _render_report(request: Request, task: TestTask):
    before = json.loads(task.smart_before_json) if task.smart_before_json else {}
    after = json.loads(task.smart_after_json) if task.smart_after_json else {}
    response = templates.TemplateResponse(request, "report.html", {"task": task,
        "device_info": json.loads(task.device_info_json) if task.device_info_json else {},
        "parameters": visible_task_parameters(task.test_type, task.parameters_json), "commands": json.loads(task.fio_command_json) if task.fio_command_json else [],
        "summary": json.loads(task.result_summary_json) if task.result_summary_json else {},
        "smart_before": before, "smart_after": after, "smart_delta": smart_delta(before, after),
        "environment": environment_info()})
    if request.query_params.get("download") == "1":
        response.headers["Content-Disposition"] = f'attachment; filename="ssd-report-{task.id}.html"'
    return response
