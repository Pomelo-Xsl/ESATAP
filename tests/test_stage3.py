import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.models.task import TestTask as TaskModel
from app.schemas.tasks import DEFAULT_QD_SCAN_DEPTHS, TestCreate as CreateSchema
from app.services.parameters import visible_task_parameters


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
    assert 'class="eligibility-row"' in device_script
    assert "device-card-actions" in device_script
    assert "device-block-reason" not in device_script
    assert "device.test_eligible ? '' : 'disabled'" in create_script


def test_all_user_operations_have_pages(client):
    for path, marker in [("/devices", "NVMe SSD 设备"), ("/tests/new", "创建测试任务"),
                         ("/tasks", "测试任务"), ("/processes", "运行监控")]:
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text


def test_stress_default_is_24_hours():
    value = CreateSchema(name="stress", device="/dev/nvme2n1", test_type="stress_rand_write",
                         destructive_confirmed=True, confirmation_device="/dev/nvme2n1")
    assert value.parameters.runtime_seconds == 86400


def test_queue_depth_scan_parameters_only_apply_to_qd_scan():
    normal = CreateSchema(name="read", device="/dev/nvme2n1", test_type="rand_read_4k",
                          parameters={"queue_depth": 32, "queue_depths": [1, 2, 4]})
    scan = CreateSchema(name="scan", device="/dev/nvme2n1", test_type="qd_scan")
    custom_scan = CreateSchema(name="custom scan", device="/dev/nvme2n1", test_type="qd_scan",
                               parameters={"queue_depths": [1, 8, 64]})

    assert normal.parameters.queue_depths is None
    assert scan.parameters.queue_depths == DEFAULT_QD_SCAN_DEPTHS
    assert custom_scan.parameters.queue_depths == [1, 8, 64]


def test_visible_parameters_hide_irrelevant_queue_depth_fields():
    legacy_payload = '{"queue_depth":32,"queue_depths":[1,2,4],"runtime_seconds":60}'

    normal = visible_task_parameters("rand_read_4k", legacy_payload)
    scan = visible_task_parameters("qd_scan", legacy_payload)

    assert normal == {"queue_depth": 32, "runtime_seconds": 60}
    assert scan == {"queue_depths": [1, 2, 4], "runtime_seconds": 60}


def test_create_page_only_exposes_scan_sequence_for_qd_scan(client):
    response = client.get("/tests/new")
    root = Path(__file__).resolve().parents[1]
    create_script = (root / "app/static/js/create.js").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'id="qd-scan-options" class="span-2 d-none"' in response.text
    assert "type.value === 'qd_scan'" in create_script
    assert "parameters.queue_depths" in create_script


def test_create_page_exposes_grouped_advanced_fio_parameters(client):
    response = client.get("/tests/new")
    assert response.status_code == 200
    for marker in ["fio 高级参数", "I/O 深度、块大小与范围", "混合读写与随机访问",
                   "速率、思考时间与时延目标", "同步、校验与 TRIM", "CPU、NUMA 与 I/O 优先级",
                   "io_uring 专用参数", "日志与统计输出"]:
        assert marker in response.text
    for field in ["io_engine", "rw", "block_size_split", "random_distribution", "rate_iops",
                  "latency_target_us", "verify", "cpus_allowed", "sqthread_poll", "percentile_list"]:
        assert f'name="{field}"' in response.text


def test_every_validated_fio_parameter_is_available_in_create_page(client):
    from app.schemas.tasks import FioParameters
    response = client.get("/tests/new")
    input_names = set(re.findall(r'name="([^"]+)"', response.text))
    assert set(FioParameters.model_fields) <= input_names


def test_create_page_shows_live_full_command_preview(client):
    response = client.get("/tests/new")
    root = Path(__file__).resolve().parents[1]
    create_script = (root / "app/static/js/create.js").read_text(encoding="utf-8")
    assert "完整 fio 测试命令" in response.text
    assert 'id="command-preview"' in response.text
    assert 'id="copy-command"' in response.text
    assert "/api/tests/preview-command" in create_script
    assert "scheduleCommandPreview" in create_script
    assert "renderCommandGroups" in create_script
    assert "command-group-label" in create_script


def test_advanced_checkbox_layout_fills_available_grid_width():
    root = Path(__file__).resolve().parents[1]
    styles = (root / "app/static/css/queue.css").read_text(encoding="utf-8")
    assert "repeat(auto-fit, minmax(180px, 1fr))" in styles
    assert '.option-check input[type="checkbox"]' in styles
    assert ".check-field .check" in styles
    assert "width: 100%;" in styles


def test_all_advanced_checkbox_groups_have_aligned_field_labels(client):
    response = client.get("/tests/new")
    page = response.text
    assert 'class="toggle-grid span-' not in page
    assert page.count('class="toggle-field') == 7
    assert page.count('<span class="check-field-label">开关选项</span>') == 7


def test_warmup_time_is_visible_in_core_parameters(client):
    response = client.get("/tests/new")
    page = response.text
    core_start = page.index("核心 I/O 参数")
    advanced_start = page.index("fio 高级参数")
    ramp_time = page.index('name="ramp_time_seconds"')
    assert core_start < ramp_time < advanced_start
    assert page.count('name="ramp_time_seconds"') == 1
    assert "预热阶段不计入正式性能统计" in page


def test_parameter_grid_top_aligns_fields_with_help_text():
    root = Path(__file__).resolve().parents[1]
    styles = (root / "app/static/css/queue.css").read_text(encoding="utf-8")
    parameter_grid = styles.split(".parameter-grid {", 1)[1].split("}", 1)[0]
    assert "align-items: start;" in parameter_grid
    assert "align-items: end;" not in parameter_grid


def test_precondition_control_has_aligned_field_label(client):
    response = client.get("/tests/new")
    root = Path(__file__).resolve().parents[1]
    styles = (root / "app/static/css/queue.css").read_text(encoding="utf-8")
    assert '<span class="check-field-label">预处理操作</span>' in response.text
    assert ".check-field-label" in styles
    assert "flex-direction: column;" in styles


def test_normal_task_api_hides_legacy_queue_depth_scan_values(client):
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        task = TaskModel(name="legacy", device="/dev/nvme2n1", test_type="rand_read_4k",
                         parameters_json='{"queue_depth":32,"queue_depths":[1,2,4]}')
        db.add(task); db.commit(); test_id = task.id

    parameters = client.get(f"/api/tests/{test_id}").json()["parameters"]
    assert parameters == {"queue_depth": 32}


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


def test_api_serializes_naive_sqlite_timestamps_as_utc(client):
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        task = TaskModel(name="timezone", device="/dev/nvme2n1", test_type="rand_read_4k",
                         parameters_json="{}", status="running",
                         started_at=datetime(2026, 9, 8, 1, 2, 3))
        db.add(task); db.commit(); test_id = task.id
    payload = client.get(f"/api/tests/{test_id}").json()
    assert payload["started_at"] == "2026-09-08T01:02:03Z"


def test_live_page_formats_elapsed_time_as_clock():
    root = Path(__file__).resolve().parents[1]
    live_script = (root / "app/static/js/live.js").read_text(encoding="utf-8")
    assert "function formatElapsed" in live_script
    assert "Date.parse(task.started_at)" in live_script
