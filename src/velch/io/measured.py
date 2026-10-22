"""Reader for the rack-railway turnout measurement campaign.

Source layout (read-only, never modified)::

    E:\\齿轨测试数据\\轮轨力和位移采集\\<N>kmh-(SP|XP)-<run>\\V*#<channel>.txt
    E:\\齿轨测试数据\\加速度采集\\<N>kmh-(SP|XP)-<run>\\V*#<channel>.txt

Each ``.txt`` has exactly three columns ``(sample index, acquisition time [s],
calibrated amplitude)``.  The acquisition clock is rounded, so the uniform time
axis is rebuilt from the index; a channel whose index is not consecutive or whose
time does not match the inferred rate is rejected rather than silently resampled.

Channel semantics come from the campaign's own index documents (transcribed in
:data:`CAMPAIGN_CHANNELS`, with the provenance recorded there):

* CH01-CH06  wheel-rail force [kN] at six locations of the turnout
* CH07       broken, excluded
* CH08       rail-foot strain at the crossing nose, recorded in microstrain and
             converted here with the campaign's own convention
             (``dt_sigma = 0.210 MPa / microstrain``)
* CH09-CH15  displacement [mm] at three locations, vertical and lateral
* CH14       no passage response, excluded from comparisons

``SP`` is the uphill direction and ``XP`` the downhill one; a folder name may carry
a parenthesised real speed (``30kmh-XP-1(10KMH-XP)``) because the nominal folder
label and the achieved speed differ.  The override always wins, matching the
campaign's own analysis.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Literal, Mapping, Sequence

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - import cycle broken at run time
    from ..inverse.channels import SensorChannel, SensorPlan
    from ..inverse.observation import ChannelSpec, ObservationSet

__all__ = [
    "CAMPAIGN_CHANNELS",
    "CH01_CALIBRATION_FACTOR",
    "STRESS_MPA_PER_MICROSTRAIN",
    "CampaignChannel",
    "CampaignCondition",
    "MeasuredIOError",
    "campaign_plan",
    "condition_windows",
    "event_window",
    "iter_conditions",
    "load_observations",
    "parse_condition",
    "read_channel",
    "read_record",
    "si_scale",
]

FORCE_DISPLACEMENT_RATE_HZ = 5120.0
CH01_CALIBRATION_FACTOR = 0.00707 / 0.00741
STRESS_MPA_PER_MICROSTRAIN = 0.210
MIN_SAMPLES = 100
TIME_TOLERANCE_S = 0.002

_FOLDER = re.compile(r"^(?P<base>\d+)\s*kmh-(?P<slope>SP|XP)-(?P<run>\d+)", re.IGNORECASE)
_OVERRIDE = re.compile(r"\((?P<speed>\d+)\s*KMH", re.IGNORECASE)
_CHANNEL = re.compile(r"#0*(?P<channel>\d+)\.txt$", re.IGNORECASE)

UnitSystem = Literal["raw", "si"]


class MeasuredIOError(ValueError):
    """Raised when a raw acquisition file cannot be interpreted consistently."""


@dataclass(frozen=True)
class CampaignCondition:
    folder: Path
    speed_kmh: int
    slope: str
    run: int

    @property
    def label(self) -> str:
        direction = "uphill" if self.slope == "SP" else "downhill"
        return f"{self.speed_kmh:>2d} km/h {direction} run {self.run}"

    @property
    def slug(self) -> str:
        return f"{self.slope}_{self.speed_kmh:02d}kmh_run{self.run}"


@dataclass(frozen=True)
class CampaignChannel:
    channel: int
    name: str
    kind: str
    quantity: str
    location: str
    unit: str
    usable: bool = True
    note: str = ""

    @property
    def si_unit(self) -> str:
        return {"kN": "N", "mm": "m", "MPa": "Pa", "m/s^2": "m/s^2"}[self.unit]


#: The campaign sensor map, transcribed from
#: ``E:\\齿轨测试数据\\实测数据出图代码\\单通道图片索引.md`` (channel/location/unit
#: table) and from ``处理说明与初步发现.md`` (CH01 re-calibration, CH07 damage,
#: CH14 no-response).  Nothing here is inferred: every location string is a literal
#: translation of that index table.
CAMPAIGN_CHANNELS: tuple[CampaignChannel, ...] = (
    CampaignChannel(1, "force_z_straight_stock", "force",
                    "vertical wheel-rail force",
                    "straight stock rail (直基本轨侧垂向)", "kN"),
    CampaignChannel(2, "force_y_straight_stock", "force",
                    "lateral wheel-rail force",
                    "straight stock rail (直基本轨侧横向)", "kN"),
    CampaignChannel(3, "force_z_curved_stock", "force",
                    "vertical wheel-rail force",
                    "curved stock rail (曲基本轨侧垂向)", "kN"),
    CampaignChannel(4, "force_z_lead_curve", "force",
                    "vertical wheel-rail force",
                    "lead curve (导曲线段垂向)", "kN"),
    CampaignChannel(5, "force_y_lead_curve", "force",
                    "lateral wheel-rail force",
                    "lead curve (直导曲线段横向)", "kN"),
    CampaignChannel(6, "force_z_crossing_nose", "force",
                    "vertical wheel-rail force",
                    "crossing nose (心轨处垂向)", "kN"),
    CampaignChannel(7, "force_spare", "force", "not used",
                    "damaged sensor (CH07 确认损坏)", "kN", usable=False,
                    note="channel documented as damaged; never loaded"),
    CampaignChannel(8, "stress_crossing_nose", "strain", "rail-foot stress",
                    "crossing nose rail foot (心轨处轨底应力)", "MPa",
                    note=f"recorded in microstrain; converted with "
                         f"{STRESS_MPA_PER_MICROSTRAIN:.3f} MPa per microstrain"),
    CampaignChannel(9, "disp_z_switch_point", "displacement",
                    "vertical rail displacement", "switch point (尖轨处垂向)", "mm"),
    CampaignChannel(10, "disp_y_switch_point", "displacement",
                    "lateral rail displacement", "switch point (尖轨处横向)", "mm"),
    CampaignChannel(11, "disp_z_lead_curve", "displacement",
                    "vertical rail displacement", "lead curve (导曲线处垂向)", "mm"),
    CampaignChannel(12, "disp_y_lead_curve", "displacement",
                    "lateral rail displacement", "lead curve (导曲线处横向)", "mm"),
    CampaignChannel(13, "disp_z_frog", "displacement",
                    "vertical rail displacement", "crossing panel (辙叉区垂向)", "mm"),
    CampaignChannel(14, "disp_spare", "displacement", "not used",
                    "no passage response (CH14 疑似故障)", "mm", usable=False,
                    note="event/quiet RMS ratio ~1.00 in all six runs; excluded"),
    CampaignChannel(15, "disp_y_frog", "displacement",
                    "lateral rail displacement", "crossing panel (辙叉区横向)", "mm"),
)

_BY_CHANNEL = {c.channel: c for c in CAMPAIGN_CHANNELS}
_SI_SCALE = {"kN": 1.0e3, "mm": 1.0e-3, "MPa": 1.0e6, "m/s^2": 1.0}


def si_scale(unit: str) -> float:
    try:
        return _SI_SCALE[unit]
    except KeyError:  # pragma: no cover - guarded by CampaignChannel
        raise MeasuredIOError(f"no SI conversion for unit {unit!r}") from None


def parse_condition(folder: str | Path) -> CampaignCondition:
    """Interpret a campaign folder name into speed, slope and run."""

    path = Path(folder)
    found = _FOLDER.match(path.name)
    if found is None:
        raise MeasuredIOError(f"cannot interpret campaign folder {path.name!r}")
    override = _OVERRIDE.search(path.name)
    speed = int(override.group("speed")) if override else int(found.group("base"))
    return CampaignCondition(path, speed, found.group("slope").upper(), int(found.group("run")))


def campaign_plan(*, unit_system: UnitSystem = "raw",
                  channels: Sequence[int] | None = None,
                  sample_rate_hz: float = FORCE_DISPLACEMENT_RATE_HZ) -> SensorPlan:
    """Sensor plan of this campaign, optionally restricted to some channels.

    ``sigma`` values are the campaign's own quiet-segment noise floors where they are
    known (force ~0.05-1.3 kN depending on channel, displacement ~0.01 mm) and are
    deliberately left at zero (unknown) otherwise instead of being invented.
    """

    from ..inverse.channels import SensorChannel, SensorPlan

    # ``None`` means "the campaign's usable channels": CH07 is documented damaged
    # and CH14 has no passage response, so asking for the full set by default would
    # raise on every call instead of describing the campaign.
    if channels is None:
        wanted = {channel for channel, spec in _BY_CHANNEL.items() if spec.usable}
    else:
        wanted = {int(c) for c in channels}
    unknown = wanted - set(_BY_CHANNEL)
    if unknown:
        raise MeasuredIOError(f"campaign has no channel(s) {sorted(unknown)}")
    out: list[SensorChannel] = []
    for channel in sorted(wanted):
        spec = _BY_CHANNEL[channel]
        if not spec.usable:
            raise MeasuredIOError(f"CH{channel:02d} is not usable: {spec.note}")
        unit = spec.si_unit if unit_system == "si" else spec.unit
        out.append(SensorChannel(name=spec.name, kind=spec.kind, unit=unit,
                                 sample_rate_hz=sample_rate_hz, sigma=0.0,
                                 location=spec.location))
    return SensorPlan(tuple(out),
                      notes=("rack-railway turnout campaign; CH07 damaged and CH14 "
                             "without passage response are never included"))


def read_channel(folder: str | Path, channel: int,
                 *, rate_hz: float | None = None,
                 repair_clock: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Read one raw channel as ``(time_s, amplitude)`` in recorded units.

    The time axis is rebuilt from the sample index; the recorded clock is only used
    to infer the nominal rate and to cross-check it against the index.

    Some campaign exports repeat a timestamp or step backwards where the acquisition
    buffer rolled over (``30KMH-SP-1`` does this on every channel).  ``repair_clock``
    drops those offending samples -- keeping the first of a repeated stamp -- and
    rebuilds the index, which is the only repair that cannot invent samples.  The
    default stays strict so a silently damaged record never enters a comparison.
    """

    path = Path(folder)
    if not path.is_dir():
        raise MeasuredIOError(f"campaign folder not found: {path}")
    candidates = [p for p in sorted(path.glob("*.txt"))
                  if (m := _CHANNEL.search(p.name)) and int(m.group("channel")) == int(channel)
                  and p.stat().st_size > 0]
    if not candidates:
        raise MeasuredIOError(f"{path.name}: no non-empty file for CH{int(channel):02d}")
    if len(candidates) > 1:
        names = ", ".join(p.name for p in candidates)
        raise MeasuredIOError(f"{path.name}: several non-empty files for CH{int(channel):02d}: {names}")

    source = candidates[0]
    data = np.loadtxt(source, dtype=np.float64, ndmin=2)
    if data.ndim != 2 or data.shape[1] != 3:
        raise MeasuredIOError(f"{source.name}: expected three columns, got {data.shape}")
    if data.shape[0] < MIN_SAMPLES:
        raise MeasuredIOError(f"{source.name}: only {data.shape[0]} samples")
    index, clock, value = data[:, 0], data[:, 1], data[:, 2]
    if not np.isfinite(data).all():
        raise MeasuredIOError(f"{source.name}: non-finite sample")
    if not np.array_equal(index, np.arange(index.shape[0], dtype=index.dtype)):
        raise MeasuredIOError(f"{source.name}: sample index is not consecutive from zero")
    if np.any(np.diff(clock) <= 0.0):
        if not repair_clock:
            raise MeasuredIOError(f"{source.name}: acquisition time is not strictly increasing")
        keep = np.concatenate(([True], np.diff(clock) > 0.0))
        clock, value = clock[keep], value[keep]
        if clock.shape[0] < MIN_SAMPLES:
            raise MeasuredIOError(
                f"{source.name}: only {clock.shape[0]} samples survive clock repair")
        # Dropping a rolled-over stamp always leaves a hole, so re-indexing onto a
        # uniform grid would *invent* samples.  Keep the recorded stamps instead and
        # let the record be slightly non-uniform.
        if int(channel) == 1:
            value = value * CH01_CALIBRATION_FACTOR
        return clock, value

    rate = float(rate_hz) if rate_hz else round((index[-1] - index[0]) / (clock[-1] - clock[0]))
    if rate <= 0:
        raise MeasuredIOError(f"{source.name}: inferred rate is not positive")
    time = clock[0] + index / rate
    worst = float(np.max(np.abs(time - clock)))
    if worst > TIME_TOLERANCE_S:
        raise MeasuredIOError(
            f"{source.name}: recorded clock deviates from the {rate:g} Hz model by {worst:.4f} s")

    if int(channel) == 1:
        value = value * CH01_CALIBRATION_FACTOR
    return time, value


def event_window(time_s: np.ndarray, values: np.ndarray, *,
                 block_s: float = 0.25, quiet_s: float = 1.0,
                 active_factor: float = 3.0) -> tuple[float, float]:
    """Locate the passage window from one channel, as the campaign does.

    The campaign detects the core passage from a rolling RMS of CH01 and then widens
    it with the outermost significant pulse of the neighbouring force channels.  This
    entry point reproduces only the first half (rolling-RMS core window) so a campaign
    folder without a published window can still be anchored; the widening step stays
    an explicit caller decision.
    """

    time_s = np.asarray(time_s, float)
    values = np.asarray(values, float)
    if time_s.shape != values.shape:
        raise MeasuredIOError("time and values must share a shape")
    count = max(2, int(round(block_s / float(np.median(np.diff(time_s))))))
    blocks = values[: (values.shape[0] // count) * count].reshape(-1, count)
    rms = np.sqrt(np.mean(blocks ** 2, axis=1))
    centres = time_s[: blocks.shape[0] * count : count] + block_s / 2.0
    head = max(1, int(round(quiet_s / block_s)))
    threshold = active_factor * float(np.median(np.concatenate((rms[:head], rms[-head:]))))
    active = np.flatnonzero(rms > threshold)
    if active.size == 0:
        raise MeasuredIOError("no passage block exceeds the quiet-segment threshold")
    start = float(centres[active[0]] - block_s / 2.0)
    stop = float(centres[active[-1]] + block_s / 2.0)
    return start, stop


def condition_windows(csv_path: str | Path) -> dict[str, tuple[float, float]]:
    """Read the campaign's published ``condition_windows.csv``.

    Returns ``{folder_name: (event_start_s, event_end_s)}`` so a comparison uses the
    campaign's own windows instead of re-detecting them.
    """

    path = Path(csv_path)
    if not path.is_file():
        raise MeasuredIOError(f"window table not found: {path}")
    text = path.read_text(encoding="utf-8-sig").splitlines()
    if not text:
        raise MeasuredIOError(f"window table is empty: {path}")
    header = [h.strip() for h in text[0].split(",")]
    try:
        folder_at = header.index("folder")
        start_at = header.index("event_start_s")
        stop_at = header.index("event_end_s")
    except ValueError:
        raise MeasuredIOError("window table lacks folder/event_start_s/event_end_s") from None
    windows: dict[str, tuple[float, float]] = {}
    for line in text[1:]:
        fields = line.split(",")
        if len(fields) <= max(folder_at, start_at, stop_at):
            continue
        try:
            windows[fields[folder_at].strip()] = (float(fields[start_at]), float(fields[stop_at]))
        except ValueError:
            continue
    return windows


def read_record(folder: str | Path, *,
                channels: Sequence[int] | None = None,
                window: tuple[float, float] | None = None,
                unit_system: UnitSystem = "si",
                windows_table: str | Path | None = None,
                processed: bool = False,
                repair_clock: bool = False) -> tuple[CampaignCondition, np.ndarray,
                                                     dict[str, np.ndarray],
                                                     dict[str, str]]:
    """Read one campaign record into ``(condition, time, {name: values}, provenance)``.

    ``window`` (or the matching row of ``windows_table``) slices every channel on the
    shared time axis, so all channels of one comparison stay strictly simultaneous.
    Values are returned in SI by default; convert back for reporting with
    :func:`si_scale`.

    ``processed`` additionally applies the conditioning the campaign's published
    figures use (:data:`PROCESSING_LOWPASS_HZ` and :data:`OFFSET_CHANNELS`). Leave it
    off when the comparison must see the raw record; turn it on when the target
    numbers come from those figures.
    """

    condition = parse_condition(folder)
    wanted = [c.channel for c in CAMPAIGN_CHANNELS if c.usable] if channels is None else [int(c) for c in channels]
    if windows_table is not None and window is None:
        window = condition_windows(windows_table).get(condition.folder.name)

    time: np.ndarray | None = None
    columns: dict[str, np.ndarray] = {}
    provenance: dict[str, str] = {
        "source": str(condition.folder),
        "condition": condition.label,
        "campaign": "rack-railway turnout (E:/齿轨测试数据)",
        "unit_system": unit_system,
        "rate_hz": f"{FORCE_DISPLACEMENT_RATE_HZ:g}",
    }
    if window is not None:
        provenance["window_s"] = f"{window[0]:.4f}-{window[1]:.4f}"
    else:
        provenance["window_s"] = "full record"

    for channel in wanted:
        spec = _BY_CHANNEL[channel]
        if not spec.usable:
            continue
        channel_time, values = read_channel(condition.folder, channel, repair_clock=repair_clock)
        if time is None:
            time = channel_time
        elif channel_time.shape != time.shape or np.max(np.abs(channel_time - time)) > TIME_TOLERANCE_S:
            raise MeasuredIOError(f"CH{channel:02d} shares no time axis with the first channel")
        if spec.kind == "strain":
            quiet = float(np.median(values[: int(round(1.0 * FORCE_DISPLACEMENT_RATE_HZ))]))
            values = STRESS_MPA_PER_MICROSTRAIN * (values - quiet)
            provenance[f"CH{channel:02d}"] = (f"{spec.location}; microstrain centred on the "
                                              f"first-second median, x{STRESS_MPA_PER_MICROSTRAIN:.3f} MPa")
        else:
            provenance[f"CH{channel:02d}"] = f"{spec.location}; {spec.unit}"
        if processed:
            corner = PROCESSING_LOWPASS_HZ.get(spec.kind)
            if corner is not None:
                rate = 1.0 / float(np.median(np.diff(channel_time)))
                values = lowpass(values, rate, corner)
                provenance[f"CH{channel:02d}"] += f"; low-pass {corner:g} Hz"
        columns[spec.name] = values * (si_scale(spec.unit) if unit_system == "si" else 1.0)

    if time is None:
        raise MeasuredIOError(f"{condition.folder.name}: no usable channel selected")
    if window is not None:
        start, stop = float(window[0]), float(window[1])
        if stop <= start:
            raise MeasuredIOError(f"invalid window {window}")
        keep = (time >= start) & (time <= stop)
        if int(keep.sum()) < MIN_SAMPLES:
            raise MeasuredIOError(f"{condition.folder.name}: window {window} keeps too few samples")
        time = time[keep]
        columns = {name: values[keep] for name, values in columns.items()}
    if processed:
        for name in columns:
            if name in OFFSET_CHANNELS:
                columns[name] = columns[name] - float(np.median(columns[name]))
                provenance[name] = provenance.get(name, "") + "; window median removed"
    return condition, time, columns, provenance


def load_observations(folder: str | Path, *,
                      channels: Sequence[int] | None = None,
                      window: tuple[float, float] | None = None,
                      windows_table: str | Path | None = None,
                      unit_system: UnitSystem = "si",
                      role: Literal["data", "check"] = "data",
                      processed: bool = False) -> ObservationSet:
    """Read a campaign record straight into an :class:`ObservationSet`."""

    from ..inverse.observation import ChannelSpec, ObservationSet

    condition, time, columns, provenance = read_record(
        folder, channels=channels, window=window, unit_system=unit_system,
        windows_table=windows_table, processed=processed)
    names = list(columns)
    specs: list[ChannelSpec] = []
    for name in names:
        spec = next(c for c in CAMPAIGN_CHANNELS if c.name == name)
        unit = spec.si_unit if unit_system == "si" else spec.unit
        specs.append(ChannelSpec(name=name, unit=unit, role=role,
                                 frame=spec.location,
                                 sample_rate_hz=FORCE_DISPLACEMENT_RATE_HZ))
    values = np.array([columns[name] for name in names], float)
    provenance.setdefault("condition_slug", condition.slug)
    return ObservationSet(tuple(specs), np.asarray(time, float), values, "s", provenance)


PROCESSING_LOWPASS_HZ = {"displacement": 10.0, "acceleration": 5.0}
"""Low-pass corner the campaign's published figures use, by channel kind.

Applied only on request (``read_record(processed=True)``); the raw reader stays
raw. Reproducing the 2026-10-19 figure numbers needs these corners: without them
the displacement peaks come out 10-20 % high because the raw record still carries
the sensor's high-frequency content.
"""

OFFSET_CHANNELS = frozenset({"disp_y_switch_point"})
"""Channels whose published value is a deflected-window offset, not absolute.

``CH10`` swings +-22.8 mm over the whole record (the lateral sensor has no target
outside the passage), while the documented passage peak is -0.25..-0.35 mm, so the
figure set removes the window median. Subtracting the *record* median would not do
it: the offset only exists around the passage.
"""


def lowpass(values: np.ndarray, rate_hz: float, corner_hz: float) -> np.ndarray:
    """Zero-phase 4th-order Butterworth low-pass, the campaign's conditioning."""

    from scipy.signal import butter, sosfiltfilt

    if corner_hz <= 0.0 or values.size < 16 or rate_hz <= 2.0 * corner_hz:
        return np.asarray(values, dtype=float)
    sos = butter(4, corner_hz / (0.5 * rate_hz), btype="low", output="sos")
    return sosfiltfilt(sos, np.asarray(values, dtype=float))


def iter_conditions(root: str | Path, *, recursive: bool = True) -> tuple[CampaignCondition, ...]:
    """Every campaign folder under ``root`` that holds at least one readable channel."""

    base = Path(root)
    if not base.is_dir():
        raise MeasuredIOError(f"campaign root not found: {base}")
    pattern = "**/*.txt" if recursive else "*.txt"
    folders: dict[Path, None] = {}
    for path in sorted(base.glob(pattern)):
        if _CHANNEL.search(path.name) and path.stat().st_size > 0:
            folders.setdefault(path.parent, None)
    conditions = []
    for folder in folders:
        try:
            conditions.append(parse_condition(folder))
        except MeasuredIOError:
            continue
    return tuple(conditions)
