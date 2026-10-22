"""Screen ⑦「三维模型」: draw the rails and wheelsets the case actually describes.

What this screen is
-------------------
The geometry comes from the profile files the case references, i.e. the same files the
solver reads, and the transforms copy ``contact._absolute_arrays`` (wheel centre plus
rotated meridian point, rail datum plus profile point).  So the picture is the model the
solver integrates, not an illustration of it.

What it is **not**
------------------
* There is no contact search here: the view does not compute penetration or show contact
  patches.  Those numbers live on the ⑤ 评价 screen, which reads the solver's output.
* The carbody/bogie outline is schematic (the case carries mass and inertia, not a body
  drawing), and the screen says so in its note line.
* Rail bodies are drawn one per body (stock/switch/wing/point).  Merging them into one
  surface would hide exactly the step the solver is careful to keep.

The screen is deliberately lazy: it loads a case only when it is shown, and re-uses the
parsed case for every redraw (a 13.5 MB case costs about half a second to parse).
"""
from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any

import numpy as np

from ..vehicle import load_vehicle_case
from . import model3d, store, theme
from .screen import Screen
from .widgets import ui_font

MAX_FRAMES = 4000

try:  # Matplotlib is an optional dependency of the UI, not of the solver.
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure

    MATPLOTLIB_3D = True
    IMPORT_PROBLEM = ""
except Exception as exc:  # pragma: no cover - depends on the environment
    FigureCanvasTkAgg = None  # type: ignore[assignment]
    Figure = None  # type: ignore[assignment]
    MATPLOTLIB_3D = False
    IMPORT_PROBLEM = f"{type(exc).__name__}: {exc}"

VIEWS: dict[str, tuple[float, float]] = {
    "等轴": (22.0, -58.0),
    "正视": (6.0, -90.0),
    "侧视": (6.0, 0.0),
    "俯视": (86.0, -90.0),
}


class Model3DScreen(Screen):
    name = "model3d"
    title = "三维模型"
    subtitle = "钢轨型面与车轮的三维视图；几何取自本算例引用的型面文件，与求解器同源"
    shortcut = "Ctrl+7"
    hint = "选算例 → 定里程窗 → 重画；叠加运行后可拖时间滑块看车轮姿态"

    def _build(self) -> None:
        self.cases: list[store.CaseInfo] = []
        self.runs: list[store.RunInfo] = []
        self.series: store.Series | None = None
        self.scene: model3d.Scene | None = None
        self._case_key: tuple[str, float] | None = None
        self._case: Any = None
        self._frames = 0
        self._last_ms = 0.0

        self.case_var = tk.StringVar()
        self.run_var = tk.StringVar(value="（不叠加运行）")
        self.start_var = tk.StringVar(value="")
        self.length_var = tk.DoubleVar(value=12.0)
        self.stations_var = tk.IntVar(value=36)
        self.points_var = tk.IntVar(value=40)
        self.spin_var = tk.IntVar(value=32)
        self.time_var = tk.DoubleVar(value=0.0)
        self.show_rails = tk.BooleanVar(value=True)
        self.show_wheels = tk.BooleanVar(value=True)
        self.show_skeleton = tk.BooleanVar(value=True)
        self.axle_vars = [tk.IntVar(value=1 if index in (1, 2) else 0) for index in range(4)]
        self.summary_var = tk.StringVar(value="未加载")
        self.notes_var = tk.StringVar(value="")

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, style="Bg.TFrame", width=int(340 * theme.SCALE))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACE["3"]))
        left.grid_propagate(False)
        left.columnconfigure(0, weight=1)

        case_card = self._card(left, "算例", 0)
        self.case_combo = ttk.Combobox(case_card, textvariable=self.case_var,
                                       state="readonly", height=18)
        self.case_combo.pack(fill="x", pady=(2, theme.SPACE["1"]))
        self.case_combo.bind("<<ComboboxSelected>>", lambda _e: self.draw())
        ttk.Button(case_card, text="刷新算例列表", style="Ghost.TButton",
                   command=self.refresh).pack(anchor="w")

        window_card = self._card(left, "里程窗与网格", 1)
        row = ttk.Frame(window_card, style="Raised.TFrame")
        row.pack(fill="x")
        ttk.Label(row, text="起点 m", style="Muted.TLabel", background=theme.RAISED,
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        ttk.Entry(row, textvariable=self.start_var, width=9, style="Field.TEntry").pack(
            side="left", padx=(theme.SPACE["1"], theme.SPACE["3"]))
        ttk.Label(row, text="长度 m", style="Muted.TLabel", background=theme.RAISED,
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        ttk.Spinbox(row, from_=1.0, to=120.0, increment=1.0, width=6,
                    textvariable=self.length_var, style="TSpinbox").pack(side="left")
        ttk.Label(window_card, text="起点留空 = 用算例自己的起始里程", style="Dim.TLabel",
                  background=theme.RAISED,
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w", pady=(2, 0))

        grid_row = ttk.Frame(window_card, style="Raised.TFrame")
        grid_row.pack(fill="x", pady=(theme.SPACE["1"], 0))
        for label, variable, high in (("站位数", self.stations_var, 200),
                                      ("横向点", self.points_var, 160),
                                      ("周向点", self.spin_var, 120)):
            cell = ttk.Frame(grid_row, style="Raised.TFrame")
            cell.pack(side="left", padx=(0, theme.SPACE["2"]))
            ttk.Label(cell, text=label, style="Muted.TLabel", background=theme.RAISED,
                      font=ui_font(theme.FONT_SIZE["micro"])).pack(anchor="w")
            ttk.Spinbox(cell, from_=8, to=high, increment=4, width=5,
                        textvariable=variable, style="TSpinbox").pack()

        axles = ttk.Frame(window_card, style="Raised.TFrame")
        axles.pack(fill="x", pady=(theme.SPACE["1"], 0))
        ttk.Label(axles, text="轴位", style="Muted.TLabel", background=theme.RAISED,
                  font=ui_font(theme.FONT_SIZE["micro"])).pack(side="left")
        for index, variable in enumerate(self.axle_vars, start=1):
            ttk.Checkbutton(axles, text=str(index), variable=variable,
                            style="TCheckbutton").pack(side="left", padx=(2, 0))

        run_card = self._card(left, "叠加运行（看时间点）", 2)
        self.run_combo = ttk.Combobox(run_card, textvariable=self.run_var,
                                      state="readonly", height=10)
        self.run_combo.pack(fill="x", pady=(2, theme.SPACE["1"]))
        self.run_combo.bind("<<ComboboxSelected>>", lambda _e: self.load_run())
        self.time_scale = ttk.Scale(run_card, from_=0.0, to=0.0, variable=self.time_var,
                                    command=lambda _v: self.on_time())
        self.time_scale.pack(fill="x")
        self.time_label = ttk.Label(run_card, text="未叠加运行", style="Dim.TLabel",
                                    background=theme.RAISED,
                                    font=ui_font(theme.FONT_SIZE["micro"]))
        self.time_label.pack(anchor="w")

        show_card = self._card(left, "显示", 3)
        for text, variable in (("钢轨型面", self.show_rails),
                               ("车轮", self.show_wheels),
                               ("车辆骨架", self.show_skeleton)):
            ttk.Checkbutton(show_card, text=text, variable=variable,
                            style="TCheckbutton",
                            command=self.draw).pack(anchor="w")

        ttk.Label(left, textvariable=self.summary_var, style="Subtitle.TLabel",
                  background=theme.BG, wraplength=320,
                  justify="left").grid(row=4, column=0, sticky="ew", pady=(theme.SPACE["2"], 0))

        right = ttk.Frame(self, style="Bg.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(right, style="Bg.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, theme.SPACE["2"]))
        ttk.Button(toolbar, text="重画", style="Ghost.TButton",
                   command=self.draw).pack(side="left", padx=(0, theme.SPACE["1"]))
        for label in VIEWS:
            ttk.Button(toolbar, text=label, style="Ghost.TButton",
                       command=lambda name=label: self.set_view(name)).pack(
                side="left", padx=(0, theme.SPACE["1"]))
        ttk.Button(toolbar, text="PNG", style="Ghost.TButton",
                   command=self.export_figure).pack(side="left")

        self.stage = ttk.Frame(right, style="Card.TFrame")
        self.stage.grid(row=1, column=0, sticky="nsew")
        self.stage.columnconfigure(0, weight=1)
        self.stage.rowconfigure(0, weight=1)

        ttk.Label(right, text="坐标：里程 x / 横向 y / 高程 z，单位 m；虚线框为车厢轮廓（示意）",
                  style="Dim.TLabel", background=theme.BG).grid(
            row=3, column=0, sticky="w", pady=(theme.SPACE["1"], 0))
        self.notes_label = ttk.Label(right, textvariable=self.notes_var, style="Dim.TLabel",
                                     background=theme.BG, justify="left")
        self.notes_label.grid(row=2, column=0, sticky="ew", pady=(theme.SPACE["1"], 0))
        # The note is the honest caption of the drawing (schematic carbody, shared profile files).
        # A fixed 880 px wrap ran past the canvas edge and cut it mid-sentence.
        self.wrap_with(self.notes_label, right, reserve=16)

        self.axes = None
        self.canvas = None
        if MATPLOTLIB_3D:
            self.figure = Figure(figsize=(7.2, 5.4), dpi=96, facecolor=theme.SURFACE)
            self.axes = self.figure.add_subplot(111, projection="3d")
            self.canvas = FigureCanvasTkAgg(self.figure, master=self.stage)
            self.canvas.get_tk_widget().configure(background=theme.SURFACE,
                                                  highlightthickness=0)
            self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
            self.figure.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
            self._label_axes()
        else:  # pragma: no cover - only without matplotlib
            ttk.Label(self.stage, text="未安装 matplotlib，三维视图不可用。\n"
                                      "安装：pip install matplotlib",
                      style="Muted.TLabel", justify="left").grid(row=0, column=0,
                                                                 sticky="w", padx=12, pady=12)

    # -- small helpers -----------------------------------------------------
    def _card(self, parent: tk.Misc, title: str, row: int) -> ttk.Frame:
        card = ttk.Frame(parent, style="Raised.TFrame", padding=theme.SPACE["3"])
        card.grid(row=row, column=0, sticky="ew", pady=(0, theme.SPACE["2"]))
        ttk.Label(card, text=title, style="Muted.TLabel", background=theme.RAISED,
                  font=ui_font(theme.FONT_SIZE["micro"], bold=True)).pack(anchor="w")
        return card

    def _label_axes(self) -> None:
        if self.axes is None:
            return
        # These were the only hard-coded point sizes left in the interface, so ⑦ ignored
        # Ctrl+= entirely: at 130 % every other panel grew and this one stayed 9 pt.
        # 3D axis titles are placed by the renderer along the projected edges, where they land on
        # top of the rails and on each other.  The coordinate meaning is stated once in the caption
        # above the note line; the axes keep only their tick numbers.
        self.axes.set_xlabel("")
        self.axes.set_ylabel("")
        self.axes.set_zlabel("")
        self.axes.tick_params(labelsize=theme.FONT_SIZE["micro"] - 1,
                              colors=theme.INK_MUTED, pad=2)
        # Nine projected tick labels per axis do not fit in the width a 3D view leaves them; four
        # is what the eye can associate with a grid line.
        from matplotlib.ticker import MaxNLocator
        locator = MaxNLocator(nbins=4, prune=None)
        for axis in (self.axes.xaxis, self.axes.yaxis, self.axes.zaxis):
            axis.set_major_locator(locator)
        # Fill the canvas: by default a 3D axes is drawn at roughly half the panel size, which is
        # what made this screen look like a thumbnail in a large empty box.
        if hasattr(self.axes, "set_box_aspect"):
            self.axes.set_box_aspect(None, zoom=1.45)

    # -- data --------------------------------------------------------------
    def refresh(self) -> None:
        if not MATPLOTLIB_3D:
            self._detail = f"matplotlib 不可用：{IMPORT_PROBLEM}"
            self.set_rows(0, self._detail)
            return
        labels: list[str] = []
        self.cases = [item for item in store.scan_cases(hashing=False)
                      if item.kind == "vehicle" and not item.problem]
        for item in self.cases:
            labels.append(f"{item.case_id}   {item.duration_label}")
        self.case_combo.configure(values=labels)
        if labels and self.case_var.get() not in labels:
            preferred = next((text for text in labels if "frog_N_strip05" in text), labels[0])
            self.case_var.set(preferred)
        self.load_runs()
        self.draw()

    def load_runs(self) -> None:
        try:
            self.runs = store.scan_runs()
        except Exception:
            self.runs = []
        labels = ["（不叠加运行）"] + [f"{item.name}   {item.status_label}" for item in self.runs]
        self.run_combo.configure(values=labels)

    def selected_case(self) -> Path | None:
        text = self.case_var.get()
        if not text or not self.cases:
            return None
        case_id = text.split("   ")[0]
        for item in self.cases:
            if item.case_id == case_id:
                return item.path
        return None

    def _load_case(self, path: Path) -> Any:
        stamp = path.stat().st_mtime
        key = (str(path), stamp)
        if self._case_key != key or self._case is None:
            self._case = load_vehicle_case(path)
            self._case_key = key
        return self._case

    def load_run(self) -> None:
        text = self.run_var.get()
        if text.startswith("（"):
            self.series = None
            self.time_scale.configure(to=0.0)
            self.time_var.set(0.0)
            self.time_label.configure(text="未叠加运行")
            self.draw()
            return
        name = text.split("   ")[0]
        info = next((item for item in self.runs if item.name == name), None)
        if info is None:
            return
        try:
            self.series = store.read_history(info.history)
        except Exception as exc:
            self.series = None
            self.app.set_status(f"读取 history.csv 失败：{type(exc).__name__}: {exc}",
                                tone="fail")
            return
        self._frames = int(self.series.rows)
        self.time_scale.configure(to=max(0, self._frames - 1))
        self.time_var.set(0.0)
        self.on_time()

    def on_time(self) -> None:
        if self.series is None:
            return
        index = int(round(self.time_var.get()))
        index = max(0, min(index, self._frames - 1))
        stamp = float(self.series.time_s[index]) if self.series.time_s.size else 0.0
        self.time_label.configure(text=f"帧 {index + 1}/{self._frames}   t = {stamp:.4f} s")
        self.draw()

    # -- drawing -----------------------------------------------------------
    def set_view(self, name: str) -> None:
        if self.axes is None:
            return
        elevation, azimuth = VIEWS[name]
        self.axes.view_init(elev=elevation, azim=azimuth)
        self.canvas.draw_idle()

    def draw(self) -> None:
        if not MATPLOTLIB_3D or self.axes is None:
            return
        path = self.selected_case()
        if path is None:
            self.summary_var.set("没有可用的整车算例")
            return
        started = time.perf_counter()
        try:
            case = self._load_case(path)
            if self.series is not None and self._frames > 0:
                index = max(0, min(int(round(self.time_var.get())), self._frames - 1))
                states = model3d.states_from_history(case, list(self.series.values),
                                                     index, self.series.values)
            else:
                states = model3d.initial_states(case)
            axles = tuple(index + 1 for index, variable in enumerate(self.axle_vars)
                          if variable.get())
            start_text = self.start_var.get().strip()
            s_lo = float(start_text) if start_text else None
            scene = model3d.build_scene(
                path, s_lo=s_lo, length_m=float(self.length_var.get()),
                axles=axles or (1,), stations=int(self.stations_var.get()),
                points=int(self.points_var.get()), spin=int(self.spin_var.get()),
                states=states, with_wheels=bool(self.show_wheels.get()), case=case)
        except Exception as exc:
            self.summary_var.set(f"三维视图刷新失败：{type(exc).__name__}: {exc}")
            self.set_rows(0, self.summary_var.get())
            return
        self.scene = scene
        self.render(scene)
        self._last_ms = 1000.0 * (time.perf_counter() - started)
        counts = f"{len(scene.rails)} 个轨面 / {len(scene.wheels)} 个车轮 / " \
                 f"{scene.vertex_count} 顶点"
        self.summary_var.set(f"{scene.case_id}\n{counts}\n耗时 {self._last_ms:.0f} ms")
        self.notes_var.set("；".join(scene.notes))
        self.set_rows(len(scene.rails) + len(scene.wheels),
                      f"{counts}  {self._last_ms:.0f} ms  "
                      f"x {scene.x_lo_m:.2f}…{scene.x_hi_m:.2f} m")

    def render(self, scene: model3d.Scene) -> None:
        axes = self.axes
        axes.clear()
        self._label_axes()
        show_rails = bool(self.show_rails.get())
        show_wheels = bool(self.show_wheels.get())
        show_skeleton = bool(self.show_skeleton.get())
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        zs: list[np.ndarray] = []
        for grid in scene.rails:
            if not show_rails:
                break
            self._surface(grid)
            xs.append(grid.x_m.ravel())
            ys.append(grid.y_m.ravel())
            zs.append(grid.z_m.ravel())
        for grid in scene.wheels:
            if not show_wheels:
                break
            self._surface(grid, alpha=0.96)
            xs.append(grid.x_m.ravel())
            ys.append(grid.y_m.ravel())
            zs.append(grid.z_m.ravel())
        if show_skeleton:
            self._skeleton(scene.skeleton)
        if not xs:  # nothing selected: still show a frame
            self.summary_var.set("已隐藏全部面片")
        else:
            axis_x = np.concatenate(xs)
            axis_y = np.concatenate(ys)
            axis_z = np.concatenate(zs)
            span_x = max(float(axis_x.max() - axis_x.min()), 1e-6)
            span_y = max(float(axis_y.max() - axis_y.min()), 1e-6)
            span_z = max(float(axis_z.max() - axis_z.min()), 0.2)
            pad_x, pad_y, pad_z = 0.04 * span_x, 0.12 * span_y + 0.05, 0.12 * span_z + 0.1
            axes.set_xlim(float(axis_x.min()) - pad_x, float(axis_x.max()) + pad_x)
            axes.set_ylim(float(axis_y.min()) - pad_y, float(axis_y.max()) + pad_y)
            axes.set_zlim(float(axis_z.min()) - pad_z, float(axis_z.max()) + pad_z)
            axes.set_box_aspect((span_x + 2 * pad_x, span_y + 2 * pad_y,
                                 max(span_z + 2 * pad_z, 0.5)))
        axes.set_title(f"{scene.case_id}   x {scene.x_lo_m:.2f}–{scene.x_hi_m:.2f} m",
                       fontsize=theme.FONT_SIZE["tiny"], color=theme.INK)
        axes.set_facecolor(theme.SURFACE)
        for pane in (axes.xaxis, axes.yaxis, axes.zaxis):
            pane.pane.set_facecolor(theme.RAISED)
            pane.pane.set_edgecolor(theme.BORDER)
            pane._axinfo["grid"]["color"] = theme.BORDER  # noqa: SLF001 - no public API
        if self.canvas is not None:
            self.canvas.draw_idle()

    def _surface(self, grid: model3d.QuadGrid, *, alpha: float = 1.0) -> None:
        rows, columns = grid.shape
        self.axes.plot_surface(grid.x_m, grid.y_m, grid.z_m, color=grid.colour,
                               linewidth=0, antialiased=False, shade=True, alpha=alpha,
                               rcount=min(rows, 64), ccount=min(columns, 64))

    def _skeleton(self, skeleton: dict[str, Any]) -> None:
        colour = theme.INK_DIM
        half_gauge = float(skeleton["bogie_half_gauge_m"])
        z_wheel = float(skeleton["z_wheel_m"])
        z_bogie = float(skeleton["z_bogie_m"])
        bogie_length = float(skeleton["bogie_length_m"]) / 2.0
        for x_m in skeleton["axle_x_m"]:
            self.axes.plot([x_m, x_m], [-half_gauge, half_gauge], [z_wheel, z_wheel],
                           color=theme.ACCENT, linewidth=2.0)
        for centre in skeleton["bogie_x_m"]:
            for side in (-half_gauge, half_gauge):
                self.axes.plot([centre - bogie_length, centre + bogie_length],
                               [side, side], [z_bogie, z_bogie],
                               color=colour, linewidth=2.0)
            for end in (centre - bogie_length, centre + bogie_length):
                self.axes.plot([end, end], [-half_gauge, half_gauge], [z_bogie, z_bogie],
                               color=colour, linewidth=2.0)
        x0, x1, y0, y1, z0, z1 = skeleton["carbody"]
        edges = (
            ((x0, y0, z0), (x1, y0, z0)), ((x0, y1, z0), (x1, y1, z0)),
            ((x0, y0, z1), (x1, y0, z1)), ((x0, y1, z1), (x1, y1, z1)),
            ((x0, y0, z0), (x0, y1, z0)), ((x1, y0, z0), (x1, y1, z0)),
            ((x0, y0, z1), (x0, y1, z1)), ((x1, y0, z1), (x1, y1, z1)),
            ((x0, y0, z0), (x0, y0, z1)), ((x1, y0, z0), (x1, y0, z1)),
            ((x0, y1, z0), (x0, y1, z1)), ((x1, y1, z0), (x1, y1, z1)),
        )
        for start, end in edges:
            self.axes.plot([start[0], end[0]], [start[1], end[1]], [start[2], end[2]],
                           color=colour, linewidth=1.0, linestyle="--")

    # -- export ------------------------------------------------------------
    def export_figure(self) -> None:
        if not MATPLOTLIB_3D or self.figure is None:
            self.app.set_status("三维视图不可用，无法导出", tone="fail")
            return
        stem = self.scene.case_id if self.scene is not None else "model3d"
        path = filedialog.asksaveasfilename(
            parent=self, title="导出三维视图", defaultextension=".png",
            initialfile=f"{stem}_3d.png",
            filetypes=[("PNG 图片", "*.png"), ("PDF 文档", "*.pdf")])
        if not path:
            return
        try:
            self.figure.savefig(path, dpi=180, facecolor=theme.SURFACE)
        except Exception as exc:
            self.app.set_status(f"导出失败：{type(exc).__name__}: {exc}", tone="fail")
            return
        self.app.set_status(f"已导出 {path}")

    def selftest_detail(self) -> str:
        if self.scene is None:
            return self._detail or "未加载场景"
        return (f"{self.scene.case_id}  轨面 {len(self.scene.rails)}  车轮 {len(self.scene.wheels)}  "
                f"顶点 {self.scene.vertex_count}  {self._last_ms:.0f} ms")
