import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CountLineConfig:
    start: tuple[int, int]
    end: tuple[int, int]

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> "CountLineConfig":
        start = payload.get("start")
        end = payload.get("end")

        if not _is_point(start) or not _is_point(end):
            raise ValueError("Invalid line config: 'start' and 'end' must be [x, y].")

        return cls(start=(int(start[0]), int(start[1])), end=(int(end[0]), int(end[1])))

    def to_json_dict(self) -> dict[str, list[int]]:
        return {
            "start": [self.start[0], self.start[1]],
            "end": [self.end[0], self.end[1]],
        }


def load_count_line_config(path: str | Path) -> CountLineConfig:
    path_obj = Path(path)
    with path_obj.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return CountLineConfig.from_json_dict(payload)


def save_count_line_config(path: str | Path, config: CountLineConfig, extra: dict[str, Any] | None = None) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, Any] = config.to_json_dict()
    if extra:
        payload.update(extra)

    with path_obj.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _is_point(value: Any) -> bool:
    if not isinstance(value, list) and not isinstance(value, tuple):
        return False
    if len(value) != 2:
        return False
    return all(isinstance(v, int) for v in value)
