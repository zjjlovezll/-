"""证明 `vehicle_ref` 与内联 `vehicle` 完全等价：同一算例跑两遍，逐位比 `history.csv`。

这是车辆数据库的验收门，也是"批量建车"这条路的地基：只要引用能替代内联且数字不变，
新增一台车就只是新增一个 json，不必复制十个算例。

    python -X utf8 scripts/verify_vehicle_ref.py                     # 默认用 0.05 s 辙叉算例
    python -X utf8 scripts/verify_vehicle_ref.py --case <别的算例> --model CRH380A_M
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "src"
DEFAULT_CASE = "case_frog_N_strip05.json"


def _absolutise(node, base: Path) -> None:
    """派生算例可能被放到任何目录，型面引用必须先变成绝对路径。"""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "file" and isinstance(value, str) and not Path(value).is_absolute():
                node[key] = str((base / value).resolve())
            else:
                _absolutise(value, base)
    elif isinstance(node, list):
        for item in node:
            _absolutise(item, base)


def _run(case: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle",
                           str(case), "--output", str(out)],
                          cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="vehicle_ref 与内联 vehicle 的逐位等价性")
    parser.add_argument("--case", default=DEFAULT_CASE, help=f"算例文件名（默认 {DEFAULT_CASE}）")
    parser.add_argument("--model", default="CRH380A_M", help="车辆库里的 id")
    parser.add_argument("--work", default=None, help="临时目录（默认仓库下 .verify_vehicle_ref）")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(SOURCE))
    from velch.data_root import case_dir

    source = case_dir() / args.case
    if not source.is_file():
        print(f"算例不存在：{source}")
        return 2
    work = Path(args.work) if args.work else REPO / ".verify_vehicle_ref"
    if work.is_dir():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    raw = json.loads(source.read_text(encoding="utf-8"))
    inline = json.loads(json.dumps(raw))
    _absolutise(inline, source.parent)
    inline["case_id"] = f"{raw['case_id']}__inline"
    inline_path = work / "case_inline.json"
    inline_path.write_text(json.dumps(inline, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")

    referenced = json.loads(json.dumps(raw))
    _absolutise(referenced, source.parent)
    referenced.pop("vehicle")
    referenced["vehicle_ref"] = args.model
    referenced["case_id"] = f"{raw['case_id']}__ref"
    ref_path = work / "case_ref.json"
    ref_path.write_text(json.dumps(referenced, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    facts: dict[str, dict[str, object]] = {}
    for name, path in (("inline", inline_path), ("ref", ref_path)):
        out = work / f"out_{name}"
        completed = _run(path, out)
        history = out / "history.csv"
        manifest = out / "manifest.json"
        if not history.is_file() or not manifest.is_file():
            print(f"[{name}] 没跑出来（exit {completed.returncode}）")
            print((completed.stdout + completed.stderr)[-1500:])
            return 2
        summary = json.loads(manifest.read_text(encoding="utf-8")).get("summary", {})
        facts[name] = {
            "history_sha256": hashlib.sha256(history.read_bytes()).hexdigest(),
            "history_bytes": history.stat().st_size,
            "result_status": summary.get("result_status"),
            "gates_failed": summary.get("gates_failed"),
        }

    same = facts["inline"]["history_sha256"] == facts["ref"]["history_sha256"]
    print(json.dumps(facts, ensure_ascii=False, indent=2))
    print(f"history.csv 逐位相同：{'是' if same else '否'}")
    print(f"result_status：{facts['ref']['result_status']}")
    if same:
        print("VERDICT: EQUIVALENT")
        return 0
    print("VERDICT: DIFFERS")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
