"""Geometry behind the 3D view: read the case's own profiles, never re-derive physics.

The view answers one question — *what does the model actually look like where the wheel meets
the rail* — and it answers it from the same files the solver reads:

* rail surfaces come from each body's ``ProfileSeries``, swept along the station mileages;
* wheel surfaces are the case's wheel profile revolved about the axle axis, placed with the
  same roll transform ``contact._absolute_arrays`` uses;
* wheelset positions come from ``history.csv`` when a run is loaded, otherwise from the case's
  initial state.

Nothing here searches for a contact point, integrates, or looks up contact stiffness.  That is
deliberate: a picture that quietly disagreed with the solver would be worse than no picture, so
this module stays a reader of geometry and state, and the screen says so.

Sign conventions (they matter, and they are the solver's, not invented here):

* profile ``z`` is the height above the running plane: a larger ``z`` is a higher point;
* a wheel point at lateral offset ``ly`` has radius ``R = R0 - z`` from the axle centre, so the
  flange (``z < 0``) is the *largest* radius and dips below the rail top;
* a positive roll rotates ``+y`` down, exactly as ``y_abs = y_c + c*ly + s*R`` in ``contact``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from ..model import Wheel
from ..profiles import ProfileSeries
from ..vehicle import VehicleCase, load_vehicle_case

#: Schematic carbody box, in metres.  The case carries mass and inertia, not a drawing, so the
#: screen must not pretend these came from the model — they are labelled as schematic there.
CARBODY_LENGTH_M = 24.0
CARBODY_WIDTH_M = 3.0
CARBODY_HEIGHT_M = 3.2
BOGIE_LENGTH_M = 3.4

RAIL_COLOURS = ("#2f6f8f", "#3f8f6f", "#8f6f2f", "#6f4f8f", "#2f8f8f")
WHEEL_COLOUR = "#9a4a2a"


@dataclass(frozen=True)
class QuadGrid:
    """A ``(stations × points)`` patch in the track frame.  ``x/y/z`` share the shape."""

    x_m: np.ndarray
    y_m: np.ndarray
    z_m: np.ndarray
    label: str
    colour: str

    @property
    def shape(self) -> tuple[int, int]:
        return self.x_m.shape

    def extents(self) -> tuple[float, float, float, float, float, float]:
        return (float(self.x_m.min()), float(self.x_m.max()),
                float(self.y_m.min()), float(self.y_m.max()),
                float(self.z_m.min()), float(self.z_m.max()))


@dataclass(frozen=True)
class WheelState:
    """One wheelset's position and roll at the instant the view is drawn."""

    axle: int
    x_m: float
    y_m: float
    z_m: float
    roll_rad: float


@dataclass(frozen=True)
class Scene:
    case_id: str
    x_lo_m: float
    x_hi_m: float
    rails: tuple[QuadGrid, ...]
    wheels: tuple[QuadGrid, ...]
    skeleton: dict[str, Any]
    states: tuple[WheelState, ...]
    notes: tuple[str, ...] = ()

    @property
    def vertex_count(self) -> int:
        return sum(int(grid.x_m.size) for grid in (*self.rails, *self.wheels))


def axle_x_positions(case: VehicleCase, time_s: float = 0.0) -> tuple[float, ...]:
    """Longitudinal position of each wheelset centre at ``time_s``.

    The solver's own definition: start mileage, plus each axle offset, plus travel.
    """
    travel = case.vehicle.travel_speed_m_s * float(time_s)
    return tuple(case.run.x_start_m + offset + travel for offset in case.vehicle.axle_offsets_m)


def initial_states(case: VehicleCase, time_s: float = 0.0) -> tuple[WheelState, ...]:
    """Wheelsets at their case positions with the case's initial lateral/vertical offsets."""
    positions = axle_x_positions(case, time_s)
    q = case.initial_q
    states = []
    for axle in range(4):
        base = 5 * axle
        states.append(WheelState(axle=axle + 1, x_m=positions[axle],
                                 y_m=float(q[base]),
                                 z_m=case.vehicle.wheel_center_height_m + float(q[base + 1]),
                                 roll_rad=float(q[base + 2])))
    return tuple(states)


def states_from_history(case: VehicleCase, columns: Sequence[str], index: int,
                        data: dict[str, np.ndarray], time_s: float | None = None) -> tuple[WheelState, ...]:
    """Wheelsets as recorded in ``history.csv``, falling back to the initial state per channel.

    A missing channel is not an error: a rigid-track case simply has no rail displacement
    columns, and the view should still draw the wheelsets.
    """
    if time_s is None:
        time_s = float(data["time_s"][index]) if "time_s" in data else 0.0
    positions = axle_x_positions(case, time_s)
    states = []
    for axle in range(1, 5):
        def value(name: str, default: float) -> float:
            column = f"axle{axle}_{name}"
            if column in data and column in columns:
                return float(data[column][index])
            return default

        states.append(WheelState(axle=axle, x_m=positions[axle - 1],
                                 y_m=value("y_m", 0.0),
                                 z_m=case.vehicle.wheel_center_height_m + value("z_m", 0.0),
                                 roll_rad=value("roll_rad", 0.0)))
    return tuple(states)


def _evenly(values: np.ndarray, count: int) -> np.ndarray:
    if values.size <= count:
        return values
    picks = np.linspace(0, values.size - 1, count)
    return values[np.unique(np.round(picks).astype(int))]


def _station_mileages(series: ProfileSeries, s_lo: float, s_hi: float, count: int) -> np.ndarray:
    low = max(s_lo, float(series.lowest_m))
    high = min(s_hi, float(series.highest_m))
    if not high > low:
        return np.empty(0)
    candidates = np.asarray([station for station in series.mileages()
                             if low - 1e-9 <= station <= high + 1e-9], dtype=float)
    if candidates.size < 2:
        candidates = np.linspace(low, high, 2)
    return _evenly(candidates, count)


def _rail_grid(series: ProfileSeries, s_lo: float, s_hi: float, *, label: str,
               colour: str, stations: int, points: int) -> QuadGrid | None:
    mileages = _station_mileages(series, s_lo, s_hi, stations)
    if mileages.size < 2:
        return None
    samples = [series.sample(float(s), 1).profile for s in mileages]
    low = max(float(profile.y_m[0]) for profile in samples)
    high = min(float(profile.y_m[-1]) for profile in samples)
    if not high > low:
        return None
    grid = np.linspace(low, high, max(3, points))
    xs = np.repeat(mileages[:, None], grid.size, axis=1)
    ys = np.repeat(grid[None, :], mileages.size, axis=0)
    zs = np.empty_like(ys)
    for row, profile in enumerate(samples):
        zs[row] = profile.z_at(grid)
    return QuadGrid(x_m=xs, y_m=ys, z_m=zs, label=label, colour=colour)


def rail_grids(case: VehicleCase, *, s_lo: float, s_hi: float, axles: Iterable[int] = (1,),
               stations: int = 36, points: int = 48) -> tuple[QuadGrid, ...]:
    """Sweep each rail body's profile along the station mileages inside ``[s_lo, s_hi]``.

    Bodies are drawn separately on purpose: the stock rail, the switch rail, the wing rail and
    the point rail are different surfaces, and merging them is exactly the error the solver
    avoids by keeping one contact per body.
    """
    wanted = {int(axle) for axle in axles}
    grids: list[QuadGrid] = []
    for index, rail in enumerate(case.rails):
        if rail.axle_index + 1 not in wanted:
            continue
        bodies = rail.contact_bodies
        for position, body in enumerate(bodies):
            series = getattr(body, "series", None) or rail.profiles
            s_low = max(s_lo, float(getattr(body, "s_lo_m", -math.inf)))
            s_high = min(s_hi, float(getattr(body, "s_hi_m", math.inf)))
            label = f"{rail.wheel_id} 第{rail.axle_index + 1}轴 {getattr(body, 'id', rail.id)}"
            grid = _rail_grid(series, s_low, s_high, label=label,
                              colour=RAIL_COLOURS[(index + position) % len(RAIL_COLOURS)],
                              stations=stations, points=points)
            if grid is not None:
                grids.append(grid)
    return tuple(grids)


def wheel_grid(case: VehicleCase, wheel: Wheel, state: WheelState, *, spin: int = 40,
               points: int = 46) -> QuadGrid | None:
    """Revolve one wheel profile about the axle and place it at ``state``.

    ``R = R0 - z`` is the radius of each meridian point (see the module docstring), so the
    flange — the largest radius — is what dips below the rail top.
    """
    profile = wheel.profile
    lateral = wheel.lateral_offset_m + np.asarray(profile.y_m, dtype=float)
    if lateral.size > points:
        picks = np.unique(np.round(np.linspace(0, lateral.size - 1, points)).astype(int))
        lateral = lateral[picks]
        radial_z = np.asarray(profile.z_m, dtype=float)[picks]
    else:
        radial_z = np.asarray(profile.z_m, dtype=float)
    # The wheel profile stores height *below the axle centre* (about -0.413 m at the tread,
    # -0.458 m at the flange tip), so the radius of a meridian point is simply -z.  Using
    # ``R0 - z`` instead puts the whole wheel half a metre too low, which is how this was
    # caught: the contact patch has to land on the rail top.
    radius = -radial_z
    if not np.all(radius > 0.0):
        return None
    angles = np.linspace(0.0, 2.0 * math.pi, max(8, spin), endpoint=False)
    cos, sin = math.cos(state.roll_rad), math.sin(state.roll_rad)
    # local: lateral offset ly, vertical -R about the axle centre
    local_y = np.repeat(lateral[None, :], angles.size, axis=0)
    local_z = -np.repeat(radius[None, :], angles.size, axis=0)
    rotated_y = cos * local_y - sin * local_z
    rotated_z = sin * local_y + cos * local_z
    xs = state.x_m + np.repeat(radius[None, :], angles.size, axis=0) * np.sin(angles)[:, None]
    ys = state.y_m + rotated_y
    zs = state.z_m + rotated_z
    return QuadGrid(x_m=xs, y_m=ys, z_m=zs, label=f"{wheel.id} 车轮", colour=WHEEL_COLOUR)


def wheel_grids(case: VehicleCase, states: Sequence[WheelState], *, spin: int = 40,
                points: int = 46) -> tuple[QuadGrid, ...]:
    by_id = {wheel.id: wheel for wheel in case.wheels}
    grids: list[QuadGrid] = []
    for state in states:
        for wheel in by_id.values():
            grid = wheel_grid(case, wheel, state, spin=spin, points=points)
            if grid is not None:
                grids.append(grid)
    return tuple(grids)


def skeleton(case: VehicleCase, states: Sequence[WheelState]) -> dict[str, Any]:
    """Axle and bogie centre lines, plus the schematic carbody box.

    Only the longitudinal layout is derived (``wheelbase_m``, ``bogie_half_spacing_m``); the
    carbody outline is a schematic because the case carries mass and inertia rather than a
    drawing.  The screen labels it as such.
    """
    vehicle = case.vehicle
    axle_x = [state.x_m for state in states]
    centre = 0.5 * (axle_x[0] + axle_x[-1])
    bogie_x = (centre - vehicle.bogie_half_spacing_m, centre + vehicle.bogie_half_spacing_m)
    half_gauge = 0.5 * (max(wheel.lateral_offset_m for wheel in case.wheels)
                        - min(wheel.lateral_offset_m for wheel in case.wheels))
    z_wheel = float(np.mean([state.z_m for state in states]))
    z_bogie = z_wheel + 0.35
    z_body = z_wheel + 1.1
    return {
        "axle_x_m": axle_x,
        "bogie_x_m": bogie_x,
        "bogie_half_gauge_m": half_gauge,
        "z_wheel_m": z_wheel,
        "z_bogie_m": z_bogie,
        "z_carbody_m": z_body,
        "carbody": (centre - CARBODY_LENGTH_M / 2.0, centre + CARBODY_LENGTH_M / 2.0,
                    -CARBODY_WIDTH_M / 2.0, CARBODY_WIDTH_M / 2.0,
                    z_body, z_body + CARBODY_HEIGHT_M),
        "bogie_length_m": BOGIE_LENGTH_M,
    }


def build_scene(case_path: str | Path, *, s_lo: float | None = None, length_m: float = 12.0,
                axles: Iterable[int] = (1,), stations: int = 36, points: int = 48,
                spin: int = 40, states: Sequence[WheelState] | None = None,
                time_s: float = 0.0, with_wheels: bool = True,
                case: VehicleCase | None = None) -> Scene:
    """Read a case and return everything the 3D screen draws.

    ``s_lo`` defaults to the case's start mileage; the window is ``length_m`` long.  Passing
    ``states`` lets the screen animate an existing run without this module knowing about
    ``history.csv``.  ``case`` skips the load when the caller already parsed the file — a
    13.5 MB case costs about half a second to read, which is too much for a time slider.
    """
    if case is None:
        case = load_vehicle_case(case_path)
    low = float(case.run.x_start_m if s_lo is None else s_lo)
    high = low + float(length_m)
    used = tuple(states) if states is not None else initial_states(case, time_s)
    rails = rail_grids(case, s_lo=low, s_hi=high, axles=axles, stations=stations, points=points)
    wheels = wheel_grids(case, used, spin=spin, points=points) if with_wheels else ()
    notes = [
        "车辆中心线为示意尺寸：算例只给质量与惯量，不给车厢轮廓",
        "钢轨面来自本算例引用的型面文件，与求解器读取的是同一批文件",
    ]
    if not rails:
        notes.append("所选里程窗内没有钢轨型面覆盖：请把窗口移进算例的站位范围")
    return Scene(case_id=case.case_id, x_lo_m=low, x_hi_m=high, rails=rails, wheels=wheels,
                 skeleton=skeleton(case, used), states=used, notes=tuple(notes))
