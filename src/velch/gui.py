"""Tk desktop workbench around the existing Velch solvers."""
from __future__ import annotations

import json
import hashlib
import os
import queue
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .gui_support import (case_kind, csv_columns, get_value, iter_nodes,
                          plot_series, relocated_case, set_scalar, write_case)
from .model import load_case
from .profiles import load_profile
from .vehicle import load_vehicle_case


BG = "#eaf0f6"
PANEL = "#ffffff"
INK = "#233447"
MUTED = "#60758a"
ACCENT = "#1674b8"
TRACK = "#356d77"


class PlotCanvas(ttk.Frame):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=PANEL, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.draw())
        self.points: list[tuple[float, float]] = []
        self.xlabel = "time_s"
        self.ylabel = ""

    def set_series(self, points: list[tuple[float, float]], xlabel: str, ylabel: str) -> None:
        self.points, self.xlabel, self.ylabel = points, xlabel, ylabel
        self.draw()

    def draw(self) -> None:
        c = self.canvas
        c.delete("all")
        width, height = max(c.winfo_width(), 400), max(c.winfo_height(), 240)
        left, right, top, bottom = 75, width - 28, 30, height - 54
        c.create_rectangle(left, top, right, bottom, outline="#cad6e2")
        if not self.points:
            c.create_text(width / 2, height / 2, text="选择结果列以查看曲线", fill=MUTED,
                          font=("Microsoft YaHei UI", 11))
            return
        xs = [point[0] for point in self.points]
        ys = [point[1] for point in self.points]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        if xmax == xmin:
            xmax = xmin + 1
        if ymax == ymin:
            margin = max(abs(ymin) * 0.05, 1e-9)
            ymin, ymax = ymin - margin, ymax + margin
        else:
            margin = (ymax - ymin) * 0.08
            ymin, ymax = ymin - margin, ymax + margin
        for i in range(5):
            xx = left + (right - left) * i / 4
            yy = bottom - (bottom - top) * i / 4
            c.create_line(xx, top, xx, bottom, fill="#ecf1f5")
            c.create_line(left, yy, right, yy, fill="#ecf1f5")
            c.create_text(xx, bottom + 16, text=f"{xmin + (xmax - xmin) * i / 4:.4g}", fill=MUTED,
                          font=("Consolas", 9))
            c.create_text(left - 8, yy, text=f"{ymin + (ymax - ymin) * i / 4:.4g}",
                          fill=MUTED, anchor="e", font=("Consolas", 9))
        coords: list[float] = []
        for x, y in self.points:
            coords.extend((left + (x - xmin) / (xmax - xmin) * (right - left),
                           bottom - (y - ymin) / (ymax - ymin) * (bottom - top)))
        if len(coords) >= 4:
            c.create_line(*coords, fill=ACCENT, width=2)
        elif coords:
            x, y = coords
            c.create_oval(x - 3, y - 3, x + 3, y + 3, fill=ACCENT, outline="")
        c.create_text((left + right) / 2, height - 15, text=self.xlabel, fill=INK)
        c.create_text(left, 12, text=self.ylabel, fill=INK, anchor="w",
                      font=("Microsoft YaHei UI", 10, "bold"))


class VelchWorkbench:
    def __init__(self, root: tk.Tk, initial_case: Path | None = None):
        self.root = root
        root.title("Velch · 道岔动力学工作台")
        root.geometry("1380x850")
        root.minsize(1040, 640)
        root.configure(bg=BG)
        self._style()
        self.case_path: Path | None = None
        self.case_data: dict | None = None
        self.kind: str | None = None
        self.dirty = False
        self.paths: dict[str, tuple[str | int, ...]] = {}
        self.selected_path: tuple[str | int, ...] | None = None
        self.result_path: Path | None = None
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None
        self.running = False
        self.output_var = tk.StringVar()
        self.x_var = tk.StringVar(value="time_s")
        self.y_var = tk.StringVar()
        self.value_var = tk.StringVar()
        self.status_var = tk.StringVar(value="就绪")
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(120, self._poll)
        if initial_case is not None:
            self.open_case(initial_case)

    def _style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=INK,
                        font=("Microsoft YaHei UI", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=INK,
                        font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=INK,
                        font=("Microsoft YaHei UI", 17, "bold"))
        style.configure("Accent.TButton", background=ACCENT, foreground="white",
                        font=("Microsoft YaHei UI", 10, "bold"), padding=(15, 8))
        style.map("Accent.TButton", background=[("active", "#0d5f9b")])
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(9, 6))
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), rowheight=25,
                        background=PANEL, fieldbackground=PANEL)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"))
        style.configure("TNotebook", background=BG)
        style.configure("TNotebook.Tab", padding=(16, 8), font=("Microsoft YaHei UI", 10))

    def _build(self) -> None:
        header = ttk.Frame(self.root, padding=(18, 11))
        header.pack(fill="x")
        ttk.Label(header, text="Velch", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="道岔动力学研究工作台  ·  v0.4", foreground=MUTED).pack(side="left", padx=16)
        ttk.Button(header, text="打开案例", command=self.ask_open).pack(side="left", padx=3)
        ttk.Button(header, text="保存", command=self.save_case).pack(side="left", padx=3)
        ttk.Button(header, text="另存案例", command=self.save_as).pack(side="left", padx=3)
        ttk.Button(header, text="校验", command=self.validate_case).pack(side="left", padx=3)
        self.run_button = ttk.Button(header, text="▶ 运行仿真", style="Accent.TButton", command=self.run_case)
        self.run_button.pack(side="left", padx=(14, 3))
        self.stop_button = ttk.Button(header, text="停止", command=self.stop_run, state="disabled")
        self.stop_button.pack(side="left", padx=3)
        ttk.Button(header, text="载入结果", command=self.ask_result).pack(side="left", padx=3)

        output_row = ttk.Frame(self.root, padding=(18, 0, 18, 10))
        output_row.pack(fill="x")
        ttk.Label(output_row, text="输出目录").pack(side="left")
        ttk.Entry(output_row, textvariable=self.output_var).pack(side="left", fill="x", expand=True, padx=10)
        ttk.Button(output_row, text="选择", command=self.choose_output).pack(side="left")

        body = ttk.PanedWindow(self.root, orient="horizontal")
        body.pack(fill="both", expand=True, padx=12)
        left = ttk.Frame(body, style="Panel.TFrame", padding=7)
        body.add(left, weight=2)
        ttk.Label(left, text="模型与参数", style="Panel.TLabel",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(2, 8))
        tree_frame = ttk.Frame(left, style="Panel.TFrame")
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tree_frame, show="tree headings", columns=("value",), selectmode="browse")
        self.tree.heading("#0", text="对象 / 参数")
        self.tree.heading("value", text="值")
        self.tree.column("#0", width=220, minwidth=150)
        self.tree.column("value", width=150, minwidth=90)
        tree_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_y.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._select_tree)

        center = ttk.Frame(body)
        body.add(center, weight=5)
        self.tabs = ttk.Notebook(center)
        self.tabs.pack(fill="both", expand=True)
        overview = ttk.Frame(self.tabs, style="Panel.TFrame", padding=12)
        self.tabs.add(overview, text="模型概览")
        self.overview_title = ttk.Label(overview, text="打开一个 Velch 案例", style="Panel.TLabel",
                                        font=("Microsoft YaHei UI", 14, "bold"))
        self.overview_title.pack(anchor="w")
        self.overview_note = ttk.Label(overview, text="支持 v1 单轮对与 v2 四轴车辆案例", style="Panel.TLabel")
        self.overview_note.pack(anchor="w", pady=(4, 12))
        self.diagram = tk.Canvas(overview, bg=PANEL, highlightthickness=0, height=430)
        self.diagram.pack(fill="both", expand=True)
        self.diagram.bind("<Configure>", lambda _event: self._draw_diagram())
        ttk.Label(overview, text="研究提示：界面便于建模与数值检查；合成案例不代表真实道岔物理标定。",
                  style="Panel.TLabel", foreground=MUTED).pack(anchor="w", pady=(8, 0))

        results = ttk.Frame(self.tabs, style="Panel.TFrame", padding=10)
        self.tabs.add(results, text="结果曲线")
        chart_controls = ttk.Frame(results, style="Panel.TFrame")
        chart_controls.pack(fill="x", pady=(0, 8))
        ttk.Label(chart_controls, text="横轴", style="Panel.TLabel").pack(side="left")
        self.x_combo = ttk.Combobox(chart_controls, textvariable=self.x_var, state="readonly", width=27)
        self.x_combo.pack(side="left", padx=(6, 16))
        ttk.Label(chart_controls, text="纵轴", style="Panel.TLabel").pack(side="left")
        self.y_combo = ttk.Combobox(chart_controls, textvariable=self.y_var, state="readonly", width=38)
        self.y_combo.pack(side="left", padx=6)
        ttk.Button(chart_controls, text="绘图", command=self.draw_result).pack(side="left", padx=8)
        self.x_combo.bind("<<ComboboxSelected>>", lambda _event: self.draw_result())
        self.y_combo.bind("<<ComboboxSelected>>", lambda _event: self.draw_result())
        self.plot = PlotCanvas(results)
        self.plot.pack(fill="both", expand=True)
        self.result_note = ttk.Label(results, text="尚未载入结果", style="Panel.TLabel", foreground=MUTED)
        self.result_note.pack(anchor="w", pady=(8, 0))

        profiles_tab = ttk.Frame(self.tabs, style="Panel.TFrame", padding=10)
        self.tabs.add(profiles_tab, text="截面预览")
        self.profile_note = ttk.Label(profiles_tab, text="在模型树中选择 profile.file 后点击右侧“预览截面”",
                                      style="Panel.TLabel", foreground=MUTED)
        self.profile_note.pack(anchor="w", pady=(0, 8))
        self.profile_plot = PlotCanvas(profiles_tab)
        self.profile_plot.pack(fill="both", expand=True)

        inspector = ttk.Frame(body, style="Panel.TFrame", padding=12)
        body.add(inspector, weight=2)
        ttk.Label(inspector, text="属性编辑", style="Panel.TLabel",
                  font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w")
        self.path_label = ttk.Label(inspector, text="从左侧模型树选择参数", style="Panel.TLabel",
                                    wraplength=270, foreground=MUTED)
        self.path_label.pack(anchor="w", fill="x", pady=(18, 8))
        self.value_entry = ttk.Entry(inspector, textvariable=self.value_var)
        self.value_entry.pack(fill="x")
        self.value_entry.bind("<Return>", lambda _event: self.apply_edit())
        ttk.Button(inspector, text="应用参数", command=self.apply_edit).pack(anchor="w", pady=(10, 18))
        ttk.Button(inspector, text="选择轮廓文件", command=self.choose_profile).pack(anchor="w", pady=(0, 7))
        ttk.Button(inspector, text="预览截面", command=self.preview_profile).pack(anchor="w", pady=(0, 12))
        ttk.Separator(inspector).pack(fill="x", pady=5)
        ttk.Label(inspector, text="案例状态", style="Panel.TLabel",
                  font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(8, 6))
        self.info_text = tk.Text(inspector, width=31, height=17, wrap="word", bg=PANEL, fg=INK,
                                 font=("Consolas", 9), relief="flat")
        self.info_text.pack(fill="both", expand=True)
        self.info_text.configure(state="disabled")

        log_panel = ttk.Frame(self.root, padding=(14, 9))
        log_panel.pack(fill="x")
        ttk.Label(log_panel, text="运行日志").pack(anchor="w")
        self.log = tk.Text(log_panel, height=6, bg="#172636", fg="#dfebf5", relief="flat",
                           font=("Consolas", 9), wrap="word")
        self.log.pack(fill="x", pady=(5, 0))
        ttk.Label(self.root, textvariable=self.status_var, anchor="w",
                  padding=(15, 5)).pack(fill="x")

    def _append_log(self, message: str) -> None:
        self.log.insert("end", message.rstrip() + "\n")
        self.log.see("end")

    def _set_info(self, text: str) -> None:
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", text)
        self.info_text.configure(state="disabled")

    def ask_open(self) -> None:
        filename = filedialog.askopenfilename(title="打开 Velch 案例", filetypes=[("JSON 案例", "*.json")])
        if filename:
            self.open_case(Path(filename))

    def open_case(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            kind = case_kind(data)
            (load_vehicle_case if kind == "vehicle" else load_case)(path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("案例读取失败", str(exc))
            return
        self.case_path = path.resolve()
        self.case_data = data
        self.kind = kind
        self.dirty = False
        self.output_var.set(str(path.parent / "results" / f"{path.stem}_{datetime.now():%Y%m%d_%H%M%S}"))
        self._refresh_tree()
        self._update_overview()
        self._append_log(f"打开案例: {self.case_path}")
        self.status_var.set(f"已加载 · {data.get('case_id', path.stem)}")

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.paths.clear()
        if self.case_data is None:
            return
        items: dict[tuple[str | int, ...], str] = {(): ""}
        for path, value in iter_nodes(self.case_data):
            parent = items[path[:-1]]
            key = f"[{path[-1]}]" if isinstance(path[-1], int) else str(path[-1])
            text = f"{key} ({len(value)})" if isinstance(value, (dict, list)) else key
            display = "" if isinstance(value, (dict, list)) else str(value)
            if len(display) > 34:
                display = display[:31] + "..."
            item = self.tree.insert(parent, "end", text=text, values=(display,), open=len(path) < 2)
            items[path] = item
            self.paths[item] = path

    def _select_tree(self, _event: object = None) -> None:
        selected = self.tree.selection()
        if not selected or self.case_data is None:
            return
        path = self.paths[selected[0]]
        self.selected_path = path
        value = get_value(self.case_data, path)
        self.path_label.configure(text=" / ".join(map(str, path)))
        self.value_var.set("" if isinstance(value, (dict, list)) else str(value))
        self.value_entry.configure(state="disabled" if isinstance(value, (dict, list)) else "normal")

    def apply_edit(self) -> None:
        if self.case_data is None or self.selected_path is None:
            return
        try:
            value = set_scalar(self.case_data, self.selected_path, self.value_var.get())
        except (TypeError, ValueError) as exc:
            messagebox.showerror("参数错误", str(exc))
            return
        self.dirty = True
        item = self.tree.selection()[0]
        self.tree.set(item, "value", str(value))
        self._update_overview()
        self.status_var.set("参数已修改 · 尚未保存")

    def save_case(self) -> None:
        if self.case_data is None or self.case_path is None:
            return
        try:
            write_case(self.case_path, self.case_data)
            self.dirty = False
            self._append_log(f"保存案例: {self.case_path}")
            self.status_var.set("案例已保存")
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc))

    def save_as(self) -> None:
        if self.case_data is None or self.case_path is None:
            return
        filename = filedialog.asksaveasfilename(title="另存 Velch 案例", defaultextension=".json",
                                                initialfile=f"{self.case_path.stem}_copy.json",
                                                initialdir=self.case_path.parent,
                                                filetypes=[("JSON 案例", "*.json")])
        if not filename:
            return
        target = Path(filename).resolve()
        tmp_path: Path | None = None
        try:
            data = relocated_case(self.case_data, self.case_path, target)
            with tempfile.NamedTemporaryFile("w", suffix=".json", prefix=".velch_save_",
                                             dir=target.parent, encoding="utf-8", delete=False) as stream:
                tmp_path = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2)
            (load_vehicle_case if self.kind == "vehicle" else load_case)(tmp_path)
            os.replace(tmp_path, target)
            tmp_path = None
        except (OSError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("另存失败", str(exc))
            return
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
        self.case_data, self.case_path, self.dirty = data, target, False
        self._refresh_tree()
        self._append_log(f"另存案例: {target}")
        self.status_var.set("案例已另存并校验")

    def validate_case(self) -> bool:
        if self.case_data is None or self.case_path is None:
            messagebox.showinfo("校验", "请先打开案例")
            return False
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("w", suffix=".json", prefix=".velch_check_",
                                             dir=self.case_path.parent, encoding="utf-8", delete=False) as stream:
                tmp_path = Path(stream.name)
                json.dump(self.case_data, stream, ensure_ascii=False)
            case = (load_vehicle_case if self.kind == "vehicle" else load_case)(tmp_path)
            self._set_info(f"案例: {case.case_id}\n格式: {self.case_data['schema_version']}\n"
                           f"轮廓资源: {len(case.asset_hashes)}\n输入检查: 通过\n\n"
                           "此处仅校验输入格式与资源；数值质量由运行后的 manifest 给出。")
            self._append_log("输入校验通过")
            self.status_var.set("输入校验通过")
            return True
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self._append_log(f"输入校验失败: {exc}")
            self.status_var.set("输入校验失败")
            messagebox.showerror("输入校验失败", str(exc))
            return False
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    def choose_output(self) -> None:
        selected = filedialog.askdirectory(title="选择结果输出目录")
        if selected:
            self.output_var.set(selected)

    def _selected_profile_spec(self) -> dict | None:
        if self.selected_path is None or self.case_data is None:
            return None
        path = self.selected_path
        if path and path[-1] == "file":
            path = path[:-1]
        if not path or path[-1] != "profile":
            return None
        value = get_value(self.case_data, path)
        return value if isinstance(value, dict) and "file" in value else None

    def choose_profile(self) -> None:
        spec = self._selected_profile_spec()
        if spec is None or self.case_path is None:
            messagebox.showinfo("选择轮廓", "请先在模型树选择 profile.file 参数")
            return
        chosen = filedialog.askopenfilename(title="选择轮/轨截面文件", initialdir=self.case_path.parent,
                                            filetypes=[("轮/轨截面", "*.csv *.txt *.prr"), ("所有文件", "*.*")])
        if not chosen:
            return
        file_path = Path(chosen).resolve()
        extension = file_path.suffix.lower().lstrip(".")
        if extension not in {"csv", "txt", "prr"}:
            messagebox.showerror("轮廓格式错误", "目前只支持 CSV、TXT 和 PRR")
            return
        try:
            spec["file"] = str(file_path.relative_to(self.case_path.parent))
        except ValueError:
            spec["file"] = str(file_path)
        spec["format"] = extension
        if extension == "prr":
            spec["units"] = "m"
        if "sha256" in spec:
            spec["sha256"] = hashlib.sha256(file_path.read_bytes()).hexdigest()
        self.dirty = True
        self._refresh_tree()
        self.status_var.set("轮廓文件已修改 · 尚未保存")
        self._append_log(f"选择轮廓: {file_path}")

    def preview_profile(self) -> None:
        spec = self._selected_profile_spec()
        if spec is None or self.case_path is None or self.selected_path is None:
            messagebox.showinfo("截面预览", "请先在模型树选择 profile.file 参数")
            return
        try:
            filename = Path(spec["file"])
            source = filename if filename.is_absolute() else self.case_path.parent / filename
            surface = "wheel_lower" if "wheels" in self.selected_path else "rail_top"
            scale = 0.001 if spec.get("units") == "mm" else 1.0
            profile = load_profile(source, file_format=spec["format"], surface=surface,
                                   y_scale_m=scale, z_scale_m=scale,
                                   y_sign=int(spec.get("y_sign", 1)), z_sign=int(spec.get("z_sign", 1)),
                                   y_offset_m=float(spec.get("y_offset_m", 0)),
                                   z_offset_m=float(spec.get("z_offset_m", 0)))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            messagebox.showerror("截面预览失败", str(exc))
            return
        points = list(zip(map(float, profile.y_m), map(float, profile.z_m)))
        self.profile_plot.set_series(points, "横向 y (m)", "高度 z (m)")
        self.profile_note.configure(text=f"{source} · {len(points)} 点 · 折叠重合横坐标 {profile.collapsed_points} 点")
        self.tabs.select(2)

    def run_case(self) -> None:
        if self.running or self.case_path is None or self.case_data is None:
            if self.case_path is None:
                messagebox.showinfo("运行", "请先打开案例")
            return
        if not self.validate_case():
            return
        if self.dirty:
            # Preserve the opened case and give the run a stable, auditable input file.
            snapshot = self.case_path.with_name(f"{self.case_path.stem}_gui_{datetime.now():%Y%m%d_%H%M%S_%f}.json")
            try:
                write_case(snapshot, self.case_data)
            except OSError as exc:
                messagebox.showerror("运行失败", str(exc))
                return
            run_path = snapshot
            self._append_log(f"已生成运行案例快照: {snapshot}")
        else:
            run_path = self.case_path
        output = Path(self.output_var.get().strip())
        if not str(output).strip() or str(output) == ".":
            messagebox.showerror("运行失败", "请指定输出目录")
            return
        output = output.resolve()
        command = [sys.executable, "-m", "velch", "run-vehicle" if self.kind == "vehicle" else "run",
                   str(run_path), "--output", str(output)]
        self.running = True
        self.run_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("正在运行仿真…")
        self._append_log("运行: " + " ".join(command))
        threading.Thread(target=self._run_worker, args=(command, output), daemon=True).start()

    def _run_worker(self, command: list[str], output: Path) -> None:
        try:
            env = os.environ.copy()
            source_root = str(Path(__file__).resolve().parents[1])
            env["PYTHONPATH"] = source_root + os.pathsep + env.get("PYTHONPATH", "")
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            text=True, encoding="utf-8", errors="replace", env=env)
            stdout, stderr = self.process.communicate()
            self.worker_queue.put(("done", (self.process.returncode, stdout, stderr, output)))
        except OSError as exc:
            self.worker_queue.put(("error", str(exc)))
        finally:
            self.process = None

    def _poll(self) -> None:
        try:
            while True:
                event, payload = self.worker_queue.get_nowait()
                self.running = False
                self.run_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
                if event == "error":
                    self._append_log(str(payload))
                    self.status_var.set("运行失败")
                    continue
                code, stdout, stderr, output = payload
                if stdout.strip():
                    self._append_log(stdout)
                if stderr.strip():
                    self._append_log(stderr)
                self.status_var.set("运行完成" if code == 0 else f"运行失败 · 退出码 {code}")
                history = output / "history.csv"
                if code == 0 and history.exists():
                    self.load_result(history)
        except queue.Empty:
            pass
        self.root.after(120, self._poll)

    def stop_run(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self._append_log("已请求停止求解")
            self.status_var.set("正在停止…")

    def ask_result(self) -> None:
        filename = filedialog.askopenfilename(title="载入 Velch history.csv",
                                              filetypes=[("CSV 结果", "*.csv")])
        if filename:
            self.load_result(Path(filename))

    def load_result(self, path: Path) -> None:
        try:
            columns = csv_columns(path)
            if len(columns) < 2:
                raise ValueError("结果 CSV 缺少数据列")
            manifest = path.with_name("manifest.json")
            info = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("结果读取失败", str(exc))
            return
        self.result_path = path
        self.x_combo["values"] = columns
        self.y_combo["values"] = columns
        self.x_var.set("time_s" if "time_s" in columns else columns[0])
        self.y_var.set("carbody_z_m" if "carbody_z_m" in columns else
                       next((c for c in columns if c.endswith("_normal_n")), columns[1]))
        summary = info.get("summary", {})
        self._set_info("结果: " + str(path) + "\n\n" + json.dumps(summary, ensure_ascii=False, indent=2))
        self._append_log(f"载入结果: {path}")
        self.tabs.select(1)
        self.draw_result()

    def draw_result(self) -> None:
        if self.result_path is None:
            return
        try:
            samples, count = plot_series(self.result_path, self.x_var.get(), self.y_var.get())
        except (OSError, ValueError, KeyError) as exc:
            messagebox.showerror("绘图失败", str(exc))
            return
        self.plot.set_series(samples, self.x_var.get(), self.y_var.get())
        self.result_note.configure(text=f"{self.result_path.name} · {count} 行 · 显示 {len(samples)} 个采样点")

    def _update_overview(self) -> None:
        if self.case_data is None:
            return
        data = self.case_data
        title = str(data.get("case_id", "无名称案例"))
        self.overview_title.configure(text=title)
        if self.kind == "vehicle":
            wheelsets, bogies, rails = 4, 2, len(data.get("rail_templates", []))
            track_kind = data.get("track_dynamics", {}).get("kind", "local_compliant")
            track_labels = {"rigid": "刚性轨道", "local_compliant": "局部柔度轨道", "modal": "模态轨道"}
            track_label = track_labels.get(track_kind, f"未知轨道类型：{track_kind}")
            note = f"v2 车辆 · {wheelsets} 轮对 · {bogies} 转向架 · {rails} 种轨道模板 · {track_label}"
        else:
            note = f"v1 单轮对 · {len(data.get('rails', []))} 个钢轨补丁"
        self.overview_note.configure(text=note)
        self._draw_diagram()

    def _draw_diagram(self) -> None:
        c = self.diagram
        c.delete("all")
        if self.case_data is None:
            return
        w, h = max(c.winfo_width(), 320), max(c.winfo_height(), 400)
        cx = w / 2
        def box(x: float, y: float, width: float, label: str, color: str) -> None:
            c.create_rectangle(x - width / 2, y - 22, x + width / 2, y + 22,
                               fill=color, outline="", tags="model")
            c.create_text(x, y, text=label, fill="white", font=("Microsoft YaHei UI", 10, "bold"))
        if self.kind == "vehicle":
            box(cx, 65, 220, "车体  ·  5 DOF", ACCENT)
            for center_x, bogie_no in ((cx - w * .22, 170), (cx + w * .22, 170)):
                c.create_line(cx, 88, center_x, bogie_no - 23, fill=MUTED, width=2)
                box(center_x, bogie_no, 170, "转向架  ·  5 DOF", "#41858c")
            xs = [cx - w * .33, cx - w * .11, cx + w * .11, cx + w * .33]
            for i, x in enumerate(xs):
                parent_x = cx - w * .22 if i < 2 else cx + w * .22
                c.create_line(parent_x, 193, x, 268, fill=MUTED, width=2)
                box(x, 291, 115, f"轮对 {i + 1}", "#7188a4")
                c.create_line(x, 314, x, 358, fill=MUTED, width=2)
            c.create_line(w * .1, 366, w * .9, 366, fill=TRACK, width=8)
            c.create_text(cx, 391, text="道岔轨道模板 · 轮轨接触 · 独立轨道补丁自由度", fill=TRACK,
                          font=("Microsoft YaHei UI", 10))
        else:
            box(cx, 140, 210, "轮对  ·  4 DOF", ACCENT)
            c.create_line(cx, 162, cx, 258, fill=MUTED, width=2)
            c.create_line(w * .15, 265, w * .85, 265, fill=TRACK, width=8)
            c.create_text(cx, 300, text="钢轨补丁与轮轨接触", fill=TRACK,
                          font=("Microsoft YaHei UI", 10))

    def close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        self.root.destroy()


def main() -> None:
    initial = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    root = tk.Tk()
    VelchWorkbench(root, initial)
    root.mainloop()


if __name__ == "__main__":
    main()
