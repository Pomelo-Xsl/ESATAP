import json
from unittest.mock import patch

from app.models.task import TestTask as TaskModel


def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "企业级 SSD 自动化测试" in response.text


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
