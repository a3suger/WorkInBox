from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


PROGRESS_MARKER = "WORKINBOX_PROGRESS "
ProgressCallback = Callable[[dict[str, Any]], None]


def stdout_progress(event: dict[str, Any]) -> None:
    print(f"{PROGRESS_MARKER}{json.dumps(event, ensure_ascii=False)}", flush=True)
