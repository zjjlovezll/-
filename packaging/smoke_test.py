"""Post-build smoke test for the frozen package -- the five actions PACKAGING_2026-10-22.md lists.

Run it right after ``build_installer.py`` builds ``dist_installer/Velch``:

    python -X utf8 packaging/smoke_test.py --root dist_installer/Velch

It answers one question only: *does the thing we are about to hand over actually work on this
machine, as a package?* Every step prints why it failed, and the JSON report goes to
``reports/packaging_smoke_<timestamp>.json`` so a later reader (or the release notes) can cite it.

Steps
  1. frozen UI self-test -- 7 screens, no screen error, and the log pipe proving it can spawn the
     console sibling (this is the step that catches "打包后界面里点运行没反应").
  2. frozen CLI run on a real case -- the manifest must be ``numerically_checked`` with all seven
     gates true, which also proves the packaged solver, not just the UI, is alive.
  3. missing corpus -- a data root that does not exist must produce a readable Chinese hint and a
     non-zero exit code, never a traceback.
  4. unicode + spaces in every path involved -- case JSON, working directory, output directory.
  5. install path under a read-only location -- recorded as ``skipped`` with the manual recipe,
     because copying 186 MB is not something a smoke test should hide inside a "quick" run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _run(argv: list[str], *, cwd: Path, env: dict[str, str], timeout: float) -> tuple[int, str, str]:
    started = time.monotonic()
    # Bytes, then decode: the frozen console build used to emit GBK (console code page), and
    # ``text=True`` with a UTF-8 assumption turned that into a wall of replacement characters that
    # no regex could match -- the selftest "printed nothing" only because it was unreadable.
    process = subprocess.run(
        argv, cwd=str(cwd), env=env, capture_output=True, timeout=timeout,
    )
    elapsed = time.monotonic() - started
    stdout = process.stdout.decode("utf-8", "replace")
    stderr = process.stderr.decode("utf-8", "replace")
    if "合计：" not in stdout and "velch" not in stdout.lower():
        try:  # a build that has not picked up the UTF-8 pin yet
            stdout = process.stdout.decode("gbk", "replace")
            stderr = process.stderr.decode("gbk", "replace")
        except Exception:
            pass
    return process.returncode, stdout, stderr + f"\n[elapsed {elapsed:.1f}s]"


def _env(data_root: Path | None) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if data_root is not None:
        env["VELCH_DATA_ROOT"] = str(data_root)
    return env


def step_selftest(root: Path, data_root: Path) -> dict:
    # The console build, deliberately: the windowed exe has no stdout (PyInstaller sets it to
    # None), so a piped `Velch.exe --selftest` returns exit code 0 with zero bytes captured and
    # looks like it never ran -- measured in the first packaged smoke run.
    exe = root / "velch-cli.exe"
    if not exe.is_file():
        return {"step": "selftest", "ok": False, "detail": {"reason": f"缺少 {exe}"}}
    code, out, err = _run([str(exe), "--selftest"], cwd=root, env=_env(data_root), timeout=600)
    stdout = out
    screens = re.search(r"合计：(\d+) 屏 / (\d+) 个控件 / (\d+) 行数据 / (\d+) 个屏报错", stdout)
    stream = re.search(r"子进程流式通路：收到 (\d+) 行日志，退出码 (\d+)", stdout)
    detail = {
        "exit_code": code,
        "screens": int(screens.group(1)) if screens else None,
        "controls": int(screens.group(2)) if screens else None,
        "rows": int(screens.group(3)) if screens else None,
        "screen_errors": int(screens.group(4)) if screens else None,
        "stream_lines": int(stream.group(1)) if stream else 0,
        "stream_exit": int(stream.group(2)) if stream else None,
        "stderr_tail": err.strip().splitlines()[-3:],
    }
    ok = (code == 0 and detail["screens"] == 7 and detail["screen_errors"] == 0
          and (detail["stream_lines"] or 0) > 0 and detail["stream_exit"] == 0)
    if not ok and screens is None:
        detail["reason"] = "自检输出里找不到合计行（打包版没跑起来？）"
    return {"step": "selftest", "ok": ok, "detail": detail}


def step_cli_run(root: Path, data_root: Path, work: Path, case_name: str) -> dict:
    cli = root / "velch-cli.exe"
    case = data_root / "crh380a_m" / case_name
    if not case.is_file():
        return {"step": "cli-run", "ok": True, "skipped": True,
                "detail": {"reason": f"语料未挂载，找不到 {case}"}}
    out = work / "cli_run"
    code, stdout, stderr = _run(
        [str(cli), "run-vehicle", str(case), "--output", str(out), "--fast"],
        cwd=work, env=_env(data_root), timeout=900,
    )
    manifest_path = out / "manifest.json"
    detail: dict = {"exit_code": code, "output": str(out), "manifest": manifest_path.is_file()}
    ok = code == 0 and manifest_path.is_file()
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        summary = manifest.get("summary", {})
        gates = summary.get("gates", {})
        failed = [name for name, value in gates.items() if not value]
        detail.update({
            "result_status": summary.get("result_status"),
            "gates": len(gates),
            "gates_failed": failed,
            "peak_force_n": summary.get("peak_force_n"),
            "case_snapshot": (out / "case_snapshot.json").is_file(),
        })
        ok = ok and summary.get("result_status") == "numerically_checked" and not failed
    else:
        detail["stderr_tail"] = stderr.strip().splitlines()[-4:]
    return {"step": "cli-run", "ok": ok, "detail": detail}


def step_missing_corpus(root: Path, work: Path, case_name: str, data_root: Path) -> dict:
    cli = root / "velch-cli.exe"
    broken = work / "no_corpus_here"
    broken.mkdir(parents=True, exist_ok=True)
    # ``agent doctor`` is the command whose job is to explain the environment, and its case check
    # reads the data root -- so it is the honest probe for "corpus missing".  (Running a case with
    # a broken VELCH_DATA_ROOT proves nothing: the case path and its relative profile references
    # resolve from the file itself, so it succeeds either way.  Cost me one false PASS.)
    code, stdout, stderr = _run(
        [str(cli), "agent", "doctor"], cwd=work, env=_env(broken), timeout=300,
    )
    text = stdout + stderr
    detail = {
        "exit_code": code,
        "mentions_data_root": "VELCH_DATA_ROOT" in text,
        "mentions_marker": ".velch-data.json" in text,
        "traceback": "Traceback (most recent call last)" in text,
        "tail": text.strip().splitlines()[-4:],
    }
    ok = (code != 0 and detail["mentions_data_root"] and not detail["traceback"])
    return {"step": "missing-corpus", "ok": ok, "detail": detail}


def step_unicode_paths(root: Path, data_root: Path, work: Path, case_name: str) -> dict:
    cli = root / "velch-cli.exe"
    source = data_root / "crh380a_m" / case_name
    if not source.is_file():
        return {"step": "unicode-path", "ok": True, "skipped": True,
                "detail": {"reason": f"语料未挂载，找不到 {source}"}}
    folder = work / "中文 目录 with space"
    folder.mkdir(parents=True, exist_ok=True)
    payload = json.loads(source.read_text(encoding="utf-8"))

    def absolutise(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "file" and isinstance(value, str):
                    node[key] = str((source.parent / value).resolve())
                else:
                    absolutise(value)
        elif isinstance(node, list):
            for item in node:
                absolutise(item)

    absolutise(payload)
    case = folder / "case_中文 副本.json"
    case.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out = folder / "输出 目录"
    code, stdout, stderr = _run(
        [str(cli), "run-vehicle", str(case), "--output", str(out), "--fast"],
        cwd=folder, env=_env(data_root), timeout=900,
    )
    manifest_path = out / "manifest.json"
    detail = {"exit_code": code, "case": str(case), "output": str(out),
              "manifest": manifest_path.is_file()}
    ok = code == 0 and manifest_path.is_file()
    if not ok:
        detail["stderr_tail"] = stderr.strip().splitlines()[-4:]
    return {"step": "unicode-path", "ok": ok, "detail": detail}


def step_readonly_install(root: Path) -> dict:
    return {"step": "readonly-install", "ok": True, "skipped": True,
            "detail": {"reason": "需要把 186 MB 安装目录复制到只读位置，属手工步骤（见 PACKAGING 文档）。"
                                 "只读安装时唯一要验证的是：语料标记写在 %LOCALAPPDATA%\\Velch，"
                                 "而不是安装目录。"}}


def main() -> int:
    parser = argparse.ArgumentParser(description="打包产物冒烟验收")
    parser.add_argument("--root", default="dist_installer/Velch")
    parser.add_argument("--data", default="")
    parser.add_argument("--case", default="case_frog_N_strip05.json")
    parser.add_argument("--out", default="")
    arguments = parser.parse_args()

    repository = Path(__file__).resolve().parent.parent
    root = Path(arguments.root)
    if not root.is_absolute():
        root = repository / root
    data_arg = arguments.data or os.environ.get("VELCH_DATA_ROOT", "")
    data_root = Path(data_arg) if data_arg else Path("")
    out = Path(arguments.out) if arguments.out else Path(tempfile.mkdtemp(prefix="velch_smoke_"))
    out.mkdir(parents=True, exist_ok=True)

    steps = [
        step_selftest(root, data_root),
        step_cli_run(root, data_root, out, arguments.case),
        step_missing_corpus(root, out, arguments.case, data_root),
        step_unicode_paths(root, data_root, out, arguments.case),
        step_readonly_install(root),
    ]
    failed = [step for step in steps if not step["ok"]]
    skipped = [step for step in steps if step.get("skipped")]
    verdict = "ACCEPT" if not failed else "REJECT"

    reports = repository / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report_path = reports / f"packaging_smoke_{stamp}.json"
    report_path.write_text(json.dumps({"verdict": verdict, "root": str(root), "steps": steps},
                                      ensure_ascii=False, indent=2), encoding="utf-8")

    for step in steps:
        mark = "SKIP" if step.get("skipped") else ("PASS" if step["ok"] else "FAIL")
        print(f"[{mark}] {step['step']}")
        if not step["ok"]:
            print(f"       {json.dumps(step['detail'], ensure_ascii=False)[:600]}")
    print(f"\nverdict: {verdict} · {len(steps)} 步 · 失败 {len(failed)} · 跳过 {len(skipped)}")
    print(f"报告：{report_path}")
    print(f"临时输出：{out}")
    return 0 if verdict == "ACCEPT" else 2


if __name__ == "__main__":
    sys.exit(main())
