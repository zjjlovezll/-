@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
set "PYTHONUTF8=1"

rem Six-screen workbench (v0.4).  The old v0.3 workbench is still available as
rem   python -X utf8 -m velch.gui
rem and is left untouched on purpose.
python -X utf8 -m velch.ui %*
if errorlevel 1 (
    echo.
    echo Velch 界面启动失败。先做一次无窗口自检可以定位问题：
    echo     python -X utf8 -m velch.ui --selftest
    echo 常见原因：未安装 Python / 缺少 NumPy、SciPy / Python 未带 Tkinter。
    pause
)
