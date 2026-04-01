import json
from pathlib import Path
from typing import Any


def write_counter_stats(path: str, payload: dict[str, Any]) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    with path_obj.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
