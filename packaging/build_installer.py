"""Build the distributable folder and zip it: ``dist_installer/Velch-<version>-win64.zip``.

Steps, each of which can fail loudly on its own:

1. run PyInstaller with ``packaging/Velch.spec`` (two exes, one folder);
2. copy in what the build cannot know: the corpus marker template, a launcher ``.cmd`` with
   ``PYTHONUTF8=1``, and ``安装说明.txt`` (what to click, where the corpus goes);
3. write ``manifest.json`` -- every file with its size and sha256, so a support question can be
   answered by comparing hashes rather than by trusting a folder name;
4. zip the folder.

Usage: ``python -X utf8 packaging/build_installer.py [--skip-build]``
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist_installer"
WORK = ROOT / "build_installer"

LAUNCHER_CMDLET = """@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
start "" "%~dp0Velch.exe"
"""

README = """Velch 道岔动力学工作台 {version}
================================

一、怎么打开
  1. 双击 `启动 Velch.cmd`（推荐，已设好 UTF-8 环境变量）
     或直接双击 `Velch.exe`
  2. 想用命令行 / 给 AI 调用：在命令提示符里跑
         velch-cli.exe --help
         velch-cli.exe agent doctor
         velch-cli.exe agent manifest

二、算例数据放在哪
  程序**不自带**语料（模型与历史运行约 1.4 GB）。首次运行会读这个文件：
      %LOCALAPPDATA%\\Velch\\.velch-data.json
  内容形如：
      {{"data_root": "F:/velch_data"}}
  也可以设置环境变量 VELCH_DATA_ROOT，优先级更高。
  语料目录里应当有 validation\\crh380a_m\\（内含 case_*.json 与型面文件）。

三、七个屏分别回答什么
  ① 算例   有哪些算例，参数与哈希是什么
  ② 运行   选算例跑出一次运行（Ctrl+R）
  ③ 时程   这次运行的力/位移随里程或时间怎么变
  ④ 频谱   能量落在哪些频带
  ⑤ 评价   七项数值门 + 三项运用限值是否过
  ⑥ 对照   与 Simpack / 实测同轴叠加比
  ⑦ 三维   钢轨型面与车轮的三维视图

  字号：Ctrl+= 放大，Ctrl+- 缩小，Ctrl+0 还原。

四、这个版本能做什么、不能做什么
  能：读算例、跑仿真、看结果、算频谱与限值、读 Simpack 的 .spck/.prr 得到只读几何目录。
  不能：不会把 Simpack 的数自动写进算例（那会改动物理标定）；尚未用实测数据标定；
        与 Simpack 的对照是报告，不是"导入即等价"。

五、卸载
  直接删除整个文件夹即可，程序不写注册表。
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from velch import __version__
    return __version__


def build() -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    command = [sys.executable, "-X", "utf8", "-m", "PyInstaller", "--noconfirm",
               "--clean", "--log-level", "WARN",
               "--distpath", str(DIST), "--workpath", str(WORK),
               str(ROOT / "packaging" / "Velch.spec")]
    print("running:", " ".join(command))
    started = time.time()
    completed = subprocess.run(command, cwd=str(ROOT), check=False)
    print(f"pyinstaller exit={completed.returncode} in {time.time() - started:.1f}s")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return DIST / "Velch"


def decorate(folder: Path, version: str) -> None:
    (folder / "启动 Velch.cmd").write_text(LAUNCHER_CMDLET, encoding="utf-8", newline="\r\n")
    (folder / "安装说明.txt").write_text(README.format(version=version), encoding="utf-8", newline="\r\n")
    template = {"data_root": "F:/velch_data/validation"}
    (folder / ".velch-data.example.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def manifest(folder: Path, version: str) -> Path:
    entries = []
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            entries.append({"path": path.relative_to(folder).as_posix(),
                            "bytes": path.stat().st_size, "sha256": _sha256(path)})
    payload = {"product": "Velch", "version": version, "built": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "python": sys.version.split()[0], "files": entries,
               "total_bytes": sum(item["bytes"] for item in entries)}
    target = folder / "manifest.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return target


def zip_folder(folder: Path, version: str) -> Path:
    target = folder.parent / f"Velch-{version}-win64.zip"
    if target.exists():
        target.unlink()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, (Path(folder.name) / path.relative_to(folder)).as_posix())
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="build the Velch installer folder and zip")
    parser.add_argument("--skip-build", action="store_true", help="reuse the existing folder")
    args = parser.parse_args(argv)

    version = _version()
    folder = DIST / "Velch"
    if not args.skip_build:
        folder = build()
    if not folder.is_dir():
        print(f"missing build output: {folder}", file=sys.stderr)
        return 2
    decorate(folder, version)
    manifest_path = manifest(folder, version)
    total = json.loads(manifest_path.read_text(encoding="utf-8"))["total_bytes"]
    archive = zip_folder(folder, version)
    print(f"folder : {folder}  ({total / 1e6:.1f} MB)")
    print(f"zip    : {archive}  ({archive.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
