from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    app_name: str = "企业级 SSD 自动化测试与分析平台"
    version: str = "1.0.0"
    database_url: str = os.getenv(
        "SSD_PLATFORM_DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'ssd_platform.db'}"
    )
    results_dir: Path = Path(os.getenv("SSD_PLATFORM_RESULTS_DIR", str(BASE_DIR / "results")))
    default_stress_seconds: int = int(os.getenv("SSD_PLATFORM_DEFAULT_STRESS_SECONDS", "86400"))
    allow_file_targets: bool = os.getenv("SSD_PLATFORM_ALLOW_FILE_TARGETS", "false").lower() == "true"


settings = Settings()

