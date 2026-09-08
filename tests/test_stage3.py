import json
from pathlib import Path
from unittest.mock import patch

from app.models.task import TestTask as TaskModel


def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Enterprise SSD Automated Testing and Analysis Platform" in response.text
    assert 'href="/docs"' not in response.text


def test_dashboard_uses_single_line_english_product_title(client):
    response = client.get("/")
    assert '<h1 class="hero-title">Enterprise SSD Automated Testing and Analysis Platform</h1>' in response.text


def test_device_ui_shows_eligibility_and_disables_unsafe_targets():
    root = Path(__file__).resolve().parents[1]
    device_script = (root / "app/static/js/devices.js").read_text(encoding="utf-8")
    create_script = (root / "app/static/js/create.js").read_text(encoding="utf-8")
    assert "test_eligible" in device_script and "ineligible_reasons" in device_script
    assert "d.test_eligible?'':'disabled'" in create_script


def test_all_user_operations_have_pages(client):
    for path, marker in [("/devices", "NVMe SSD 设备"), ("/tests/new", "创建测试任务"),
                         ("/tasks", "测试任务"), ("/processes", "运行监控")]:
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text


def test_stress_default_is_24_hours():
    from app.schemas.tasks import TestCreate
    value = TestCreate(name="stress", device="/dev/nvme2n1", test_type="stress_rand_write",
                       destructive_confirmed=True, confirmation_device="/dev/nvme2n1")
    assert value.parameters.runtime_seconds == 86400


def test_html_report_contains_environment_and_smart(client):
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        task = TaskModel(name="report", device="/dev/nvme2n1", test_type="rand_read_4k",
                        parameters_json='{"runtime_seconds": 1}', status="completed",
                        device_info_json='{"model":"ACME Enterprise","serial":"SN001"}',
                        smart_before_json='{"temperature":300}', smart_after_json='{"temperature":305}')
        db.add(task); db.commit(); test_id = task.id
    with patch("app.api.pages.environment_info", return_value={"fio":"fio-3.36","nvme_cli":"nvme 2.8","operating_system":"Ubuntu","python":"3.10"}):
        response = client.get(f"/api/tests/{test_id}/report")
    assert response.status_code == 200
    assert "ACME Enterprise" in response.text and "SMART 前后对比" in response.text
    assert "fio-3.36" in response.text


def test_report_download_header(client):
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        task = TaskModel(name="download", device="/dev/nvme2n1", test_type="rand_read_4k", parameters_json="{}")
        db.add(task); db.commit(); test_id = task.id
    with patch("app.api.pages.environment_info", return_value={"fio":"x","nvme_cli":"x","operating_system":"x","python":"x"}):
        response = client.get(f"/api/tests/{test_id}/report?download=1")
    assert "attachment" in response.headers["content-disposition"]


def test_frontend_report_route(client):
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        task = TaskModel(name="frontend-report", device="/dev/nvme2n1", test_type="rand_read_4k", parameters_json="{}")
        db.add(task); db.commit(); test_id = task.id
    with patch("app.api.pages.environment_info", return_value={"fio":"x","nvme_cli":"x","operating_system":"x","python":"x"}):
        response = client.get(f"/tasks/{test_id}/report")
    assert response.status_code == 200
    assert "测试报告" in response.text
    assert "V1.0" not in response.text


def test_navigation_is_vertical_sidebar(client):
    response = client.get("/devices")
    assert response.status_code == 200
    assert 'class="sidebar"' in response.text
    assert 'class="sidebar-nav"' in response.text
    assert "V1.0" not in response.text
