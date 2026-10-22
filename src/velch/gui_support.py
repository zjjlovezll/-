"""Pure data helpers for the Velch desktop interface."""
from __future__ import annotations

import copy
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterator


def case_kind(data: dict[str, Any]) -> str:
    schema = data.get("schema_version")
    if schema == "velch-vehicle-v2":
        return "vehicle"
    if schema == "velch-case-v1":
        return "wheelset"
    raise ValueError(f"不支持的算例格式: {schema!r}")


def iter_nodes(value: Any, prefix: tuple[str | int, ...] = ()) -> Iterator[tuple[tuple[str | int, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = (*prefix, key)
            yield path, child
            yield from iter_nodes(child, path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            path = (*prefix, index)
            yield path, child
            yield from iter_nodes(child, path)


def get_value(data: Any, path: tuple[str | int, ...]) -> Any:
    current = data
    for part in path:
        current = current[part]
    return current


def parse_scalar(text: str, previous: Any) -> Any:
    if isinstance(previous, bool):
        normalized = text.strip().lower()
        if normalized in {"true", "1", "是", "yes"}:
            return True
        if normalized in {"false", "0", "否", "no"}:
            return False
        raise ValueError("布尔值请输入 true 或 false")
    if isinstance(previous, int):
        return int(text.strip())
    if isinstance(previous, float):
        result = float(text.strip())
        if not math.isfinite(result):
            raise ValueError("数值必须是有限数")
        return result
    if isinstance(previous, str):
        return text
    if previous is None:
        return None if text.strip().lower() in {"null", "none"} else text
    raise TypeError("只能编辑单个文本、数字或布尔参数")


def set_scalar(data: dict[str, Any], path: tuple[str | int, ...], text: str) -> Any:
    if not path:
        raise ValueError("请选择一个参数")
    parent = get_value(data, path[:-1])
    previous = parent[path[-1]]
    if isinstance(previous, (dict, list)):
        raise TypeError("请选择树中的具体参数")
    value = parse_scalar(text, previous)
    parent[path[-1]] = value
    return value


def relocated_case(data: dict[str, Any], source: Path, target: Path) -> dict[str, Any]:
    """Keep referenced profiles valid when a JSON case is saved elsewhere."""
    result = copy.deepcopy(data)
    if source.parent.resolve() == target.parent.resolve():
        return result
    for path, value in iter_nodes(result):
        if path and path[-1] == "profile" and isinstance(value, dict) and "file" in value:
            profile = Path(value["file"])
            if not profile.is_absolute():
                value["file"] = str((source.parent / profile).resolve())
    return result


def write_case(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_columns(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return next(csv.reader(stream))


def plot_series(path: Path, x_column: str, y_column: str, max_points: int = 3000) -> tuple[list[tuple[float, float]], int]:
    """Stream CSV; retain extrema while bounding plot memory."""
    if max_points < 4:
        raise ValueError("max_points must be >= 4")
    samples: list[tuple[float, float]] = []
    row_count = 0
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if x_column not in (reader.fieldnames or []) or y_column not in (reader.fieldnames or []):
            raise KeyError("曲线列不在结果文件中")
        for row in reader:
            row_count += 1
            try:
                x, y = float(row[x_column]), float(row[y_column])
            except (ValueError, TypeError):
                continue
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
            samples.append((x, y))
            if len(samples) > max_points:
                compacted: list[tuple[float, float]] = []
                for start in range(0, len(samples), 8):
                    block = samples[start:start + 8]
                    if not block:
                        continue
                    indices = {0, len(block) - 1,
                               min(range(len(block)), key=lambda i: block[i][1]),
                               max(range(len(block)), key=lambda i: block[i][1])}
                    compacted.extend(block[i] for i in sorted(indices))
                samples = compacted
    return samples, row_count
