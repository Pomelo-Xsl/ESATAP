from __future__ import annotations

import json
from typing import Any


def visible_task_parameters(test_type: str, payload: str | dict[str, Any]) -> dict[str, Any]:
    """Return only parameters that apply to the selected test type."""
    parameters = json.loads(payload) if isinstance(payload, str) else dict(payload)
    if test_type == "qd_scan":
        parameters.pop("queue_depth", None)
    else:
        parameters.pop("queue_depths", None)
    return parameters
