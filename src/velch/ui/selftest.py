"""``--selftest``: build the window, load every screen, print what really loaded.

This is the smoke test the UI ships with, because the interesting failure mode of a Tk
app is not "it crashed on import" but "the screen opened and silently showed nothing".
So the report is built from the live widget tree (control counts) plus the numbers each
screen actually loaded (rows, channels, bands, gates), never from a static claim.

Two guarantees:

* exit code 0 whether or not Tk works here — a machine with no display gets a clear
  reason and a data-only report instead of a traceback;
* nothing is started that costs real time — the only subprocess is ``python -c`` printing
  two lines, which still exercises the whole spawn → queue → dispatch → log path.
"""
from __future__ import annotations

import json
import sys
import time
import traceback

from . import store

STREAM_PROBE = ("import sys;"
                "print('velch-ui-stream-ok');"
                "print('velch-ui-stream-ok-2');"
                "print('argv0=' + sys.argv[0])")


def _parse_screens(spec: str) -> list[str]:
    """``"1,3,compare"`` → screen names in canonical order."""

    from .app import SCREENS

    names = [entry[0] for entry in SCREENS]
    if not spec.strip():
        return names
    wanted: set[str] = set()
    for token in spec.replace("，", ",").split(","):
        token = token.strip()
        if not token:
            continue
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(names):
                wanted.add(names[index])
        elif token in names:
            wanted.add(token)
        else:
            raise SystemExit(f"未知屏：{token}（可用 1-6 或 {', '.join(names)}）")
    return [name for name in names if name in wanted]


def _pump(root, seconds: float) -> None:
    """Let Tk process events for ``seconds`` without blocking the interpreter."""

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            root.update()
        except Exception:  # window already gone
            return
        time.sleep(0.02)


def _settle(app, root, budget: float = 90.0) -> bool:
    """Wait until no background job is in flight; returns False on timeout."""

    end = time.monotonic() + budget
    quiet = 0
    while time.monotonic() < end:
        try:
            root.update()
        except Exception:
            return False
        busy = app.state == "running"
        if not busy and (app.process is None or not app.process.running):
            quiet += 1
            if quiet >= 3:  # a few idle cycles so late callbacks still land
                return True
        else:
            quiet = 0
        time.sleep(0.02)
    return False


def _data_evidence() -> dict:
    """Numbers that come straight from the artifact store, with Tk out of the picture."""

    from . import store as st

    evidence: dict = {"screens": {}, "errors": []}
    try:
        cases = st.scan_cases(hashing=False)
        hashed = st.scan_cases(hashing=True) if cases else []
        evidence["cases"] = {
            "files": len(cases),
            "with_purpose": sum(1 for case in cases if case.purpose),
            "with_dof": sum(1 for case in cases if case.dof),
            "with_sha256": sum(1 for case in hashed if case.sha256),
            "problem": sum(1 for case in cases if case.problem),
        }
    except Exception as exc:
        evidence["errors"].append(f"算例扫描失败: {type(exc).__name__}: {exc}")

    try:
        runs = st.scan_runs()
        with_manifest = [run for run in runs if not run.problem]
        with_history = [run for run in runs if run.columns]
        evidence["runs"] = {
            "dirs": len(runs),
            "with_manifest": len(with_manifest),
            "with_history": len(with_history),
            "max_columns": max((run.columns for run in runs), default=0),
            "gates_known": sum(1 for run in with_manifest if run.gates),
        }
        if with_history:
            target = with_history[0]
            columns = [name for name in st.history_columns(target.path / "history.csv")
                       if name != "time_s"]
            series = st.read_history(target.path, ["time_s", "axle1_right_normal_n"])
            evidence["timeseries"] = {
                "run": target.name,
                "channels": len(columns),
                "groups": len(st.group_channels(columns)),
                "samples": int(series.values["time_s"].size),
                "rate_hz": round(series.rate_hz, 2),
            }
            try:
                result = st.spectrum(series, "axle1_right_normal_n", 5.0, 1000.0)
                evidence["spectrum"] = {
                    "bands": len(result.levels),
                    "low_hz": result.low_hz,
                    "high_hz": round(result.high_hz, 1),
                    "dominant_hz": result.dominant_hz,
                    "rms": round(result.metrics.rms, 3),
                }
            except Exception as exc:
                evidence["errors"].append(f"频谱计算失败: {type(exc).__name__}: {exc}")
            try:
                view = st.assess(target.path)
                evidence["assess"] = {
                    "run": target.name,
                    "samples": view.samples,
                    "pass": view.passed,
                    "checks": {key: (round(float(val.get("value") or 0.0), 4),
                                     round(float(val.get("limit") or 0.0), 4),
                                     bool(val.get("pass")))
                               for key, val in view.verdict.get("checks", {}).items()},
                    "gates": {key: bool(value)
                              for key, value in (target.gates or {}).items()},
                }
            except Exception as exc:
                evidence["errors"].append(f"评价计算失败: {type(exc).__name__}: {exc}")
            try:
                available, reason = st.simpack_available()
                evidence["compare"] = {"simpack": available, "reason": reason}
                if available:
                    ours = st.velch_reference(target.path)
                    theirs = st.simpack_reference()
                    result = st.compare(ours, theirs, None, 400)
                    evidence["compare"].update({
                        "grid_points": int(result.grid_m.size),
                        "window_m": [round(float(result.grid_m.min()), 2),
                                     round(float(result.grid_m.max()), 2)],
                        "rows": len(result.summary_rows()),
                    })
            except Exception as exc:
                evidence["errors"].append(f"对照计算失败: {type(exc).__name__}: {exc}")
    except Exception as exc:
        evidence["errors"].append(f"运行目录扫描失败: {type(exc).__name__}: {exc}")
    return evidence


def _print_evidence(evidence: dict) -> None:
    cases = evidence.get("cases") or {}
    if cases:
        print(f"  · 算例 {cases.get('files')} 个（purpose {cases.get('with_purpose')}、"
              f"自由度 {cases.get('with_dof')}、sha256 {cases.get('with_sha256')}、"
              f"解析失败 {cases.get('problem')}）")
    runs = evidence.get("runs") or {}
    if runs:
        print(f"  · 运行目录 {runs.get('dirs')} 个（manifest {runs.get('with_manifest')}、"
              f"history.csv {runs.get('with_history')}、最宽 {runs.get('max_columns')} 列、"
              f"7 项门 {runs.get('gates_known')} 个可用）")
    series = evidence.get("timeseries") or {}
    if series:
        print(f"  · 时程：{series.get('run')} → {series.get('channels')} 个通道 / "
              f"{series.get('groups')} 个单位分组 / {series.get('samples')} 行 / "
              f"{series.get('rate_hz')} Hz")
    spectrum = evidence.get("spectrum") or {}
    if spectrum:
        print(f"  · 频谱：{spectrum.get('bands')} 个 1/3 倍频程带 "
              f"（{spectrum.get('low_hz')}–{spectrum.get('high_hz')} Hz），"
              f"主导 {spectrum.get('dominant_hz')} Hz，整体 RMS {spectrum.get('rms')}")
    assess = evidence.get("assess") or {}
    if assess:
        passed = sum(1 for _v, _l, ok in assess.get("checks", {}).values() if ok)
        gates = assess.get("gates", {})
        print(f"  · 评价：{len(assess.get('checks', {}))} 项限值（通过 {passed}）/ "
              f"{len(gates)} 项门（通过 {sum(1 for ok in gates.values() if ok)}）/ "
              f"{assess.get('samples')} 个采样 · 总判定 "
              f"{'通过' if assess.get('pass') else '超限'}")
    compare = evidence.get("compare") or {}
    if compare:
        if compare.get("simpack"):
            print(f"  · 对照：Simpack 可用，{compare.get('rows')} 项差值 / "
                  f"{compare.get('grid_points')} 个共里程点 / "
                  f"{compare.get('window_m')} m")
        else:
            print(f"  · 对照：Simpack 不可用（{compare.get('reason')}），改用实测 CSV 口径")
    for message in evidence.get("errors", []):
        print(f"  ! {message}")


def _headless(reason: str, as_json: bool, screens: list[str]) -> int:
    """No Tk here: say why, still report the data plane, still exit 0."""

    evidence = _data_evidence()
    if as_json:
        print(json.dumps({"tk": False, "reason": reason, "evidence": evidence},
                         ensure_ascii=False, indent=2))
        return 0
    print("Velch UI 自检（无窗口模式）")
    print(f"[velch.ui] 未能构造 Tk 窗口：{reason}")
    print("[velch.ui] 这通常是当前会话没有可用显示或未安装 Tk；界面本身不会因此崩溃。")
    print("[velch.ui] 以下为纯数据自检结果（不建窗口、不启动求解）：")
    _print_evidence(evidence)
    print("[velch.ui] 退出码 0（未构造窗口，数据面可读）")
    return 0


def run(screens: str = "", as_json: bool = False, timeout: float = 180.0) -> int:
    """Entry point for ``--selftest``; always returns 0 unless the report is unreadable."""

    try:
        wanted = _parse_screens(screens)
    except SystemExit as exc:
        print(exc)
        return 2

    try:
        import tkinter as tk
    except Exception as exc:  # Tk not built into this interpreter
        return _headless(f"Tk 组件不可导入（{type(exc).__name__}: {exc}）", as_json, wanted)

    from velch import __version__
    from .app import build_app

    try:
        root, app = build_app(headless=True)
    except Exception as exc:  # tk.TclError: no display / no root window
        return _headless(f"{type(exc).__name__}: {exc}", as_json, wanted)

    deadline = max(10.0, float(timeout))
    started = time.monotonic()
    report: dict = {"version": __version__, "tk": True, "screens": [], "stream": {},
                    "evidence": {}}
    code = 0
    try:
        root.withdraw()
        for name in wanted:
            try:
                screen = app.show(name)
                settled = _settle(app, root, min(deadline, 60.0))
                if name == "compare":
                    compute = getattr(screen, "compute", None)
                    if callable(compute) and (store.simpack_available()[0]
                                              or False):
                        compute()
                        settled = _settle(app, root, min(deadline, 60.0)) and settled
                stats = screen.stats()
                entry = {"name": stats.name, "title": stats.title,
                         "controls": stats.controls, "rows": stats.rows,
                         "detail": stats.detail, "error": stats.error,
                         "settled": settled}
                for attribute in ("result", "view", "series"):
                    value = getattr(screen, attribute, None)
                    if value is not None and hasattr(value, "levels"):
                        entry["bands"] = len(value.levels)
                report["screens"].append(entry)
            except Exception as exc:
                report["screens"].append({
                    "name": name, "title": name, "controls": 0, "rows": 0,
                    "detail": "", "settled": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "traceback": traceback.format_exc(limit=4)})
                # a broken screen is reported in full, but it must not fail the smoke test

        # streaming probe: prove the spawn → queue → dispatch → log path end to end
        received: list[str] = []
        original = app.on_log

        def spy(line: str) -> None:
            received.append(line)
            try:
                original(line)
            except Exception:
                pass

        app.on_log = spy
        try:
            app.show("run")
            job = app.spawn([sys.executable, "-X", "utf8", "-c", STREAM_PROBE],
                            store.REPO_ROOT, owner="run")
            end = time.monotonic() + 40.0
            while time.monotonic() < end and job.running:
                try:
                    root.update()
                except Exception:
                    break
                time.sleep(0.02)
            finished = not job.running
            _pump(root, 0.4)  # let the queued log/exit events dispatch
            report["stream"] = {"lines": len(received), "exit_code": job.returncode,
                                "elapsed_s": round(job.elapsed, 2),
                                "first": received[0] if received else "",
                                "last": received[-1] if received else "",
                                "waited": finished}
        finally:
            app.on_log = original

        report["evidence"] = _data_evidence()
        report["totals"] = {
            "controls": sum(entry["controls"] for entry in report["screens"]),
            "rows": sum(entry["rows"] for entry in report["screens"]),
            "errors": sum(1 for entry in report["screens"] if entry["error"]),
        }
        report["backend"] = getattr(app, "backend_label").cget("text")
        report["wall_s"] = round(time.monotonic() - started, 2)
    finally:
        try:
            app.quit()
        except Exception:
            pass

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code

    print(f"Velch UI 自检 · 版本 {report['version']}")
    print(f"Tk 可用：是 · {report.get('backend', '')} · 全程 {report.get('wall_s')} s")
    print()
    print(f"{'屏':<16}{'控件数':>6}{'数据行':>8}  说明")
    print("-" * 96)
    for entry in report["screens"]:
        name = f"{entry['name']} ({entry['title']})"
        print(f"{name:<16}{entry['controls']:>6}{entry['rows']:>8}  {entry['detail']}")
        if entry["error"]:
            print(f"{'':<16}{'':>6}{'':>8}  [错误] {entry['error']}")
        if not entry.get("settled", True):
            print(f"{'':<16}{'':>6}{'':>8}  [注意] 后台任务在超时内未结束，数字可能不完整")
    print("-" * 96)
    totals = report["totals"]
    print(f"合计：{len(report['screens'])} 屏 / {totals['controls']} 个控件 / "
          f"{totals['rows']} 行数据 / {totals['errors']} 个屏报错")
    print()
    print("数据面（直接来自运行产物）：")
    _print_evidence(report["evidence"])
    stream = report["stream"]
    if stream:
        ok = "是" if stream.get("lines") else "否"
        print(f"  · 子进程流式通路：收到 {stream.get('lines')} 行日志，退出码 "
              f"{stream.get('exit_code')}，用时 {stream.get('elapsed_s')} s，"
              f"首行「{stream.get('first')}」（收到日志：{ok}）")
    print("退出码 0（自检完成）")
    return code
