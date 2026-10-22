"""Turn a Simpack track catalog into a Velch case — geometry from Simpack, physics from you.

What this module does, and what it refuses to do
-----------------------------------------------
The catalog (``velch inspect-simpack-track``) records *statements the Simpack model makes*: which
rail profile file sits at which mileage on which rail.  That is geometry, and it is safe to carry
over mechanically.

Everything else — masses, inertias, suspension stiffness and damping, contact stiffness, friction,
solver tolerances — decides the frozen gates (59 680.5769 N static load, 65.47 µm equilibrium,
89.68 / 170.61 kN peaks).  None of it can be read out of a ``.spck`` honestly, so this module takes
those values from a **template case you name** and only replaces the rail station table.

The output is therefore always "the template's physics, the Simpack model's rail geometry", and the
sidecar written next to it says exactly which file supplied which number.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np

from .profiles import ProfileError, load_profile
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = "velch-simpack-case-v2"
#: Crown heights match to well under a tenth of a millimetre on this model, so a crown difference
#: beyond this is worth saying out loud.  It is a *reporting* threshold, not a refusal: no crown
#: measurement predicts whether eight patches will seat (see docs/SIMPACK_IMPORT_2026-10-22.md).
#: A crown correction moves the running surface.  Imported on one side only, it is a *gauge*
#: change, and on this model the right rail asks for -74 mm…+103 mm over 80–90 m while the left rail
#: has no stations at all in that window.  Anything beyond this is refused unless the caller says
#: out loud that they mean it.
LATERAL_GAUGE_LIMIT_MM = 5.0
CROWN_WARN_MM = 0.5
CATALOG_SCHEMA = "velch-simpack-track-catalog-v1"


class SimpackCaseError(RuntimeError):
    """A catalog or template that cannot be turned into a case without guessing.

    ``detail`` carries the numbers behind the refusal so a caller (or a script) can act without
    parsing Chinese prose: "the gauge would change by 103 mm" is only useful if the reader can see
    ``worst_mm`` and the per-side station counts next to it.
    """

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.detail: dict[str, Any] = dict(detail or {})


@dataclass(frozen=True)
class CatalogStation:
    """One rail profile reference as the Simpack model states it."""

    rail: str
    side: str
    index: int
    station_m: float
    path: str
    sha256: str


@dataclass(frozen=True)
class CaseBuild:
    """What was written, and what the caller should say about it."""

    case_path: Path
    sidecar_path: Path
    station_count: int
    dropped_duplicates: int
    shift_m: float
    profile_set_sha256: str
    template: str
    model: str
    profiles_from: str = "simpack"
    crown_delta_mm: dict[str, Any] | None = None
    crown_warning: str | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "case": str(self.case_path),
            "sidecar": str(self.sidecar_path),
            "station_count": self.station_count,
            "dropped_duplicates": self.dropped_duplicates,
            "shift_m": round(self.shift_m, 6),
            "profile_set_sha256": self.profile_set_sha256,
            "template": self.template,
            "simpack_model": self.model,
            "physics_source": "template case (explicit); Simpack supplies rail geometry only",
            "profiles_from": self.profiles_from,
            "crown_delta_mm": self.crown_delta_mm,
            "crown_warning": self.crown_warning,
            "simpack_dynamics_imported": False,
        }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_catalog(path: str | Path) -> dict[str, Any]:
    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise SimpackCaseError(f"catalog not found: {catalog_path}")
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SimpackCaseError(f"{catalog_path} is not JSON: {error}") from error
    if catalog.get("schema_version") != CATALOG_SCHEMA:
        raise SimpackCaseError(
            f"{catalog_path} is {catalog.get('schema_version')!r}, expected {CATALOG_SCHEMA!r}")
    summary = catalog.get("summary") or {}
    if not summary.get("geometry_readable"):
        missing = summary.get("missing_profile_references", "?")
        raise SimpackCaseError(
            "the catalog says geometry_readable=false "
            f"(missing_profile_references={missing}); fix the model root before deriving a case")
    return catalog


def stations(catalog: dict[str, Any], *, side: str | None = None,
             rail: str | None = None) -> list[CatalogStation]:
    raw: Iterable[dict[str, Any]] = catalog.get("profile_references") or []
    chosen: list[CatalogStation] = []
    for entry in raw:
        if side is not None and entry.get("side") != side:
            continue
        if rail is not None and entry.get("rail") != rail:
            continue
        chosen.append(
            CatalogStation(
                rail=str(entry.get("rail", "")),
                side=str(entry.get("side", "")),
                index=int(entry.get("index", 0)),
                station_m=float(entry.get("station_m", 0.0)),
                path=str(entry.get("path", "")),
                sha256=str(entry.get("sha256", "")),
            )
        )
    chosen.sort(key=lambda item: (item.rail, item.station_m, item.index))
    if not chosen:
        raise SimpackCaseError(
            f"the catalog has no profile references for side={side!r} rail={rail!r}")
    return chosen


def _deduplicate(entries: Sequence[CatalogStation]) -> tuple[list[CatalogStation], int]:
    """Keep one station per mileage.

    The turnout model states two different surfaces at the same mileage (the switch blade and the
    stock rail).  ``ProfileSeries`` interpolates one surface per station, so a duplicate cannot be
    represented; the first one wins and the sidecar records how many were dropped, because that is
    a real loss of information rather than a tidy-up.
    """

    seen: dict[float, CatalogStation] = {}
    for entry in entries:
        key = round(entry.station_m, 9)
        seen.setdefault(key, entry)
    kept = sorted(seen.values(), key=lambda item: item.station_m)
    return kept, len(entries) - len(kept)


def _thin(entries: Sequence[CatalogStation], sample: int | None) -> list[CatalogStation]:
    if sample is None or sample <= 0 or sample >= len(entries):
        return list(entries)
    if sample == 1:
        return [entries[0]]
    step = (len(entries) - 1) / (sample - 1)
    picked = [entries[round(index * step)] for index in range(sample)]
    unique: list[CatalogStation] = []
    for entry in picked:
        if not unique or entry.station_m != unique[-1].station_m:
            unique.append(entry)
    return unique


def _crown_of(spec: dict[str, Any]) -> tuple[float, float] | None:
    """The lowest measured point of a rail-top profile, and where it sits laterally.

    Sampling at a fixed lateral offset was the earlier mistake: the crown of a turnout section moves
    laterally by tens of millimetres, so a fixed-offset sample reads the *flank* (≈30 mm above the
    crown on this model) and its value tracks the crown's lateral shift, not its height. Comparing
    crowns compares the thing the wheel actually rides on.
    """

    try:
        profile = load_profile(Path(spec["file"]), file_format=spec.get("format", "prr"),
                               surface="rail_top", y_sign=int(spec.get("y_sign", 1)),
                               z_sign=int(spec.get("z_sign", 1)),
                               y_offset_m=float(spec.get("y_offset_m", 0.0)))
    except (ProfileError, OSError, ValueError):
        return None
    z = np.asarray(profile.z_m, dtype=float)
    y = np.asarray(profile.y_m, dtype=float)
    if z.size == 0:
        return None
    index = int(np.argmin(z))
    return float(z[index]), float(y[index])


def _gauge_implication(catalog: list[dict[str, Any]], *, side: str, chosen_entries,
                       profile_template: dict[str, Any],
                       other_template: dict[str, Any] | None) -> dict[str, Any] | None:
    """Gauge change implied by importing this side's crown lateral positions.

    ``None`` when nothing can be measured.  The other side is measured from the catalog too: a
    correction is only a *placement* when both rails move; on its own it widens or narrows the
    gauge, and a 100 mm gauge change quietly rolls the vehicle onto one rail.
    """

    mine = [abs(delta) for delta in
            (_crown_lateral_delta(entry, profile_template) for entry in chosen_entries)
            if delta is not None]
    if not mine:
        return None
    signed = [delta for delta in
              (_crown_lateral_delta(entry, profile_template) for entry in chosen_entries)
              if delta is not None]
    worst_index = max(range(len(signed)), key=lambda index: abs(signed[index]))
    station_m = list(chosen_entries)[worst_index].station_m

    other_side = "left" if side == "right" else "right"
    other: list[float] = []
    # How many stations the other side has at all.  A turnout model often defines the varying
    # sections on one rail string only (this one: 236 right, 2 left), and then "import both sides"
    # is not an option -- there is nothing on the other side to import.  Counting it lets the
    # refusal say that instead of implying the caller forgot a flag.
    other_stations = sum(1 for item in catalog if item.get("side") == other_side)
    if other_template is not None:
        for item in catalog:
            if item.get("side") != other_side:
                continue
            entry = CatalogStation(rail=item["rail"], side=item["side"], index=int(item["index"]),
                                   station_m=float(item.get("station_m") or 0.0),
                                   path=item["path"], sha256=item.get("sha256", ""))
            if abs(entry.station_m - station_m) > 1.0:
                continue
            delta = _crown_lateral_delta(entry, other_template)
            if delta is not None:
                other.append(delta)
    other_delta = (sum(other) / len(other)) if other else 0.0
    gauge = signed[worst_index] - other_delta
    return {"max_abs_mm": round(max(mine) * 1000.0, 2),
            "signed_mm": round(signed[worst_index] * 1000.0, 2),
            "at_m": round(station_m, 3),
            "other_side_mm": round(other_delta * 1000.0, 2),
            "other_side_stations": other_stations,
            "gauge_mm": round(gauge * 1000.0, 2)}


def _crown_lateral_delta(entry: CatalogStation,
                         profile_template: dict[str, Any]) -> float | None:
    """How far this station's crown sits from the template's, laterally, in track coordinates.

    ``None`` when either crown cannot be measured.  A turnout section's crown wanders in y as the
    blade opens and closes; ignoring that shift leaves the wheel running on a flank and the contact
    point at the wrong distance from the crown, which is a difference the forces can feel even when
    the crown *height* matches to a tenth of a millimetre.
    """

    base = _crown_of(profile_template)
    if base is None:
        return None
    station = _crown_of({**profile_template, "file": entry.path})
    if station is None:
        return None
    return float(station[1]) - float(base[1])


def _crown_delta_mm(entries: Sequence[CatalogStation],
                    profile_template: dict[str, Any]) -> tuple[float, float, float] | None:
    """Worst crown-height difference (mm) and worst crown lateral shift (m) against the template.

    ``None`` means "could not be measured" — a profile whose file is missing or whose measured
    envelope is empty.  That is not the same as "no difference", and it is reported as such.
    """

    base = _crown_of(profile_template)
    if base is None:
        return None
    base_z, base_y = base
    worst_dz = 0.0
    worst_dz_at = entries[0].station_m
    worst_dy = 0.0
    measured = 0
    for entry in entries:
        point = _crown_of({**profile_template, "file": entry.path})
        if point is None:
            continue
        measured += 1
        dz = (point[0] - base_z) * 1000.0
        dy = abs(point[1] - base_y)
        if abs(dz) > abs(worst_dz):
            worst_dz, worst_dz_at = dz, entry.station_m
        worst_dy = max(worst_dy, dy)
    if measured == 0:
        return None
    return worst_dz, worst_dz_at, worst_dy


def seat_report(case_path: str | Path, *, catalog_path: str | Path | None = None,
                template_path: str | Path | None = None, x_start_m: float | None = None,
                duration_s: float | None = None, side: str | None = None,
                rail: str | None = None) -> dict[str, Any]:
    """Run the vertical preload equilibrium and report what it measured.

    This is the only honest answer to "will the imported sections seat": crown heights match to
    within 0.1 mm at windows that seat *and* at windows that do not, so no geometric threshold
    predicts it.  The solver's own equilibrium either finds eight loaded patches or it does not.

    When it does not seat, the report carries the crown measurement, the lightest/heaviest patch from
    the failure and a suggested other window (as advice, never as a substitution).
    """

    import numpy as np

    from .vehicle import load_vehicle_case
    from .vehicle_solver import (
        SimulationFailure,
        VehicleDynamics,
        _static_vertical_equilibrium,
    )

    case_file = Path(case_path)
    case = load_vehicle_case(case_file)
    dynamics = VehicleDynamics(case, contact_workers=1)
    q = np.array(case.initial_q, dtype=float)
    v = np.array(case.initial_v, dtype=float)
    report: dict[str, Any] = {"case": str(case_file), "x_start_m": case.run.x_start_m,
                              "duration_s": case.run.duration_s}
    try:
        q_eq, residual = _static_vertical_equilibrium(case, dynamics, q, v)
    except SimulationFailure as error:
        report["seats"] = False
        report["reason"] = str(error)
        if catalog_path is not None and template_path is not None and x_start_m is not None:
            try:
                catalog = load_catalog(catalog_path)
                template = json.loads(Path(template_path).read_text(encoding="utf-8"))
                picked = stations(catalog, side=side or "left", rail=rail)
                picked, _ = _deduplicate(picked)
                profile_template = dict(
                    ((template.get("rail_templates") or [{}])[0].get("stations") or [{}])[0]
                    .get("profile") or {})
                travel = float((template.get("vehicle") or {}).get("travel_speed_m_s", 0.0))
                ride = float(duration_s if duration_s is not None
                             else (template.get("run") or {}).get("duration_s", 0.0))
                crown = _crown_delta_mm(picked, profile_template)
                if crown is not None:
                    report["crown_delta_mm"] = {"max_abs": round(crown[0], 3),
                                                "at_m": round(crown[1], 3),
                                                "max_lateral_m": round(crown[2], 4)}
                report["footprint_m"] = [round(float(x_start_m) - _axle_reach_m(template), 3),
                                         round(float(x_start_m) + travel * ride, 3)]
                report["advice"] = (
                    "Crown heights do not predict this: they match to within "
                    f"{abs(crown[0]):.2f} mm over this window and it still cannot seat eight "
                    "patches. Use --keep-profiles to keep the template's running surface with the "
                    "model's station layout, or pick a window whose sections are one running surface "
                    "rather than switch/blade geometry.")
            except (SimpackCaseError, OSError, ValueError, KeyError) as advice_error:
                report["advice"] = f"could not measure alternative windows: {advice_error}"
        report["hint"] = ("nothing was wrong with the case file: the seven vertical degrees of "
                          "freedom could not seat eight patches on these sections")
        return report
    _ = q_eq
    report["seats"] = True
    report["residual_n"] = float(residual)
    _, responses = dynamics.evaluate(0.0, np.array(q_eq, dtype=float), v)
    report["per_contact_kn"] = {rail_id: round(response.normal_force_n / 1000.0, 2)
                                for rail_id, response in sorted(responses.items())}
    penetrations = [response.geometry.penetration_m for response in responses.values()
                    if response.geometry is not None]
    if penetrations:
        report["max_penetration_um"] = round(max(penetrations) * 1e6, 2)
    return report


def _axle_reach_m(template: dict[str, Any]) -> float:
    """How far behind ``x_start`` the rearmost axle sits, from the template's own geometry."""

    vehicle = template.get("vehicle") or {}
    try:
        half_spacing = float(vehicle.get("bogie_half_spacing_m", 0.0))
        wheelbase = float(vehicle.get("wheelbase_m", 0.0))
    except (TypeError, ValueError):
        return 2.0
    reach = half_spacing + wheelbase / 2.0
    return reach if reach > 0.0 else 2.0


def _template_profile(profile: dict[str, Any], path: str) -> dict[str, Any]:
    clone = dict(profile)
    clone["file"] = path
    return clone


def suggest_window(entries: Sequence[CatalogStation], profile_template: dict[str, Any], *,
                   travel_s: float, ride_s: float, span_lo: float, span_hi: float,
                   wanted_m: float, limit_mm: float = CROWN_WARN_MM,
                   reach_m: float = 2.0) -> tuple[float, float] | None:
    """The nearest model station whose ride window has crown heights within ``limit_mm``.

    Returns ``(x_start_m, max_abs_crown_delta_mm)`` or ``None`` when no candidate window qualifies.
    This is advice for the message, not a substitution: the caller still decides, and matching crowns
    do not by themselves mean the vehicle will seat.
    """

    best: tuple[float, float] | None = None
    for entry in entries:
        start = entry.station_m
        if not (span_lo <= start and start + travel_s * ride_s <= span_hi):
            continue
        lo, hi = start - reach_m, start + travel_s * ride_s
        window = [candidate for candidate in entries if lo <= candidate.station_m <= hi]
        if not window:
            continue
        delta = _crown_delta_mm(window, profile_template)
        if delta is None or abs(delta[0]) > limit_mm:
            continue
        distance = abs(start - wanted_m)
        candidate = (start, abs(delta[0]))
        if best is None or distance < abs(best[0] - wanted_m):
            best = candidate
    return best


def _advice(entries: Sequence[CatalogStation], profile_template: dict[str, Any], *,
            travel_s: float, ride_s: float, span_lo: float, span_hi: float, wanted_m: float,
            limit_mm: float, reach_m: float = 2.0) -> str:
    """One sentence naming a window whose crowns match, or admitting there is none."""

    found = suggest_window(entries, profile_template, travel_s=travel_s, ride_s=ride_s,
                           span_lo=span_lo, span_hi=span_hi, wanted_m=wanted_m, limit_mm=limit_mm,
                           reach_m=reach_m)
    if found is None:
        return ("No window in this model has crown heights within "
                f"{limit_mm:.1f} mm of the template's. ")
    start, worst = found
    return (f"The nearest start whose crowns land within {limit_mm:.1f} mm is {start:.1f} m "
            f"(worst {worst:.3f} mm). ")


def build_case(*, catalog_path: str | Path, template_path: str | Path, out_path: str | Path,
               side: str = "left", rail: str | None = None, sample: int | None = None,
               x_start_m: float, duration_s: float | None = None,
               case_id: str | None = None, keep_profiles: bool = False,
               import_lateral: bool = False, allow_gauge_change: bool = False) -> CaseBuild:
    """Write a case whose rail geometry comes from the catalog and whose physics comes from a case.

    ``x_start_m`` is required and must lie inside the model's own mileage span, because the station
    mileages are imported unchanged: shifting them is what makes a rail stop covering the first
    wheel position.  The sidecar records the span the case actually covers.

    ``import_lateral`` also writes each station's crown lateral position into its own
    ``y_offset_m``, so the wheel meets the crown where the model says it is instead of on a flank
    offset by the template's constant.  Off by default: it moves the running surface, and the two
    runs must be compared before either is quoted.

    This function does not judge whether the imported section will *seat*: no crown measurement
    predicts that (see ``docs/SIMPACK_IMPORT_2026-10-22.md``).  ``velch simpack-case`` therefore runs
    the vertical preload equilibrium on what it just wrote and refuses only on that measurement.
    """

    catalog = load_catalog(catalog_path)
    catalog_file = Path(catalog_path)
    template_file = Path(template_path)
    if not template_file.is_file():
        raise SimpackCaseError(f"template case not found: {template_file}")
    template = json.loads(template_file.read_text(encoding="utf-8"))

    rail_templates = template.get("rail_templates") or []
    index_of = {str(item.get("id")): position for position, item in enumerate(rail_templates)}
    if side not in index_of:
        raise SimpackCaseError(
            f"template has no rail template named {side!r}; it has {sorted(index_of)}")
    position = index_of[side]
    target = rail_templates[position]
    if target.get("bodies"):
        raise SimpackCaseError(
            f"template rail {side!r} is split into bodies; pick a single-surface template so the "
            "catalog's station table maps one-to-one")

    chosen = stations(catalog, side=side, rail=rail)
    chosen, dropped = _deduplicate(chosen)
    chosen = _thin(chosen, sample)

    missing = [entry.path for entry in chosen if not Path(entry.path).is_file()]
    if missing:
        raise SimpackCaseError(
            f"{len(missing)} catalog profile files are gone from disk, e.g. {missing[0]}")

    # Mileages stay exactly as the model states them.  Shifting them is how a rail ends up covering
    # 13.5–163.5 m while the first wheel sits at 13.5 m and the contact solver finds nothing: one
    # side then carries twice the even share and the preload equilibrium fails.  If the requested
    # start is outside the model's own span, that is a question for the caller, not a silent shift.
    span_lo, span_hi = chosen[0].station_m, chosen[-1].station_m
    travel_s = float((template.get("vehicle") or {}).get("travel_speed_m_s", 0.0))
    window_s = float(duration_s if duration_s is not None else
                     (template.get("run") or {}).get("duration_s", 0.0))
    needed_hi = float(x_start_m) + travel_s * window_s
    if not (span_lo <= float(x_start_m) and needed_hi <= span_hi):
        raise SimpackCaseError(
            f"x_start {x_start_m} m + {needed_hi - float(x_start_m):.2f} m of travel leaves the "
            f"model's coverage {span_lo}–{span_hi} m (side {side!r}); pick a start inside it")
    shift = 0.0
    profile_template = dict((target.get("stations") or [{}])[0].get("profile") or {})
    if not profile_template:
        raise SimpackCaseError(f"template rail {side!r} has no profile metadata to inherit")

    # Only the stations the wheels can reach decide whether the vehicle seats: a switch blade 26 m
    # behind the start cannot unload a wheel that never gets there.
    travel = float((template.get("vehicle") or {}).get("travel_speed_m_s", 0.0))
    ride_s = float(duration_s if duration_s is not None
                   else (template.get("run") or {}).get("duration_s", 0.0))
    # The whole vehicle has to be measured, not just the leading axle: the rear axle is 10 m behind
    # the start and rides whatever section is there.
    reach = _axle_reach_m(template)
    park_lo = float(x_start_m) - reach
    park_hi = float(x_start_m) + travel * ride_s
    in_window = [entry for entry in chosen if park_lo <= entry.station_m <= park_hi]
    crowns = None if keep_profiles else _crown_delta_mm(in_window or chosen, profile_template)
    warning = None
    if crowns is not None and abs(crowns[0]) > CROWN_WARN_MM:
        warning = (f"imported crowns differ from the template's by {crowns[0]:+.3f} mm at "
                   f"{crowns[1]:.3f} m; the run may seat, but say so before quoting it")

    # ``keep_profiles`` keeps the template's surface file and imports only the station *layout*.
    # The full import (default) mixes rail sections that were never calibrated against this vehicle,
    # and the run then fails the vertical preload equilibrium — loudly, in the summary.
    source_files = [str(profile_template.get("file", ""))] * len(chosen) if keep_profiles \
        else [entry.path for entry in chosen]
    lateral: list[tuple[float, float]] = []
    gauge: dict[str, Any] | None = None
    if import_lateral and not keep_profiles:
        other_position = 1 - rail_templates.index(target)
        other_template = None
        if 0 <= other_position < len(rail_templates):
            other_template = dict((rail_templates[other_position].get("stations") or [{}])[0]
                                  .get("profile") or {}) or None
        gauge = _gauge_implication(catalog.get("profile_references") or [], side=side,
                                   chosen_entries=chosen, profile_template=profile_template,
                                   other_template=other_template)
        if gauge is not None and abs(gauge["gauge_mm"]) > LATERAL_GAUGE_LIMIT_MM \
                and not allow_gauge_change:
            raise SimpackCaseError(
                f"importing this side's crown lateral positions changes the gauge by "
                f"{gauge['gauge_mm']:+.1f} mm at {gauge['at_m']:.3f} m (this side "
                f"{gauge['signed_mm']:+.1f} mm, other side {gauge['other_side_mm']:+.1f} mm), "
                f"beyond the {LATERAL_GAUGE_LIMIT_MM:.0f} mm a run can absorb: on one side a "
                "placement correction is a gauge change and rolls the vehicle onto one rail. "
                + (
                    f"This model defines only {gauge['other_side_stations']} station(s) on the "
                    f"{'left' if side == 'right' else 'right'} rail, so importing both sides is not "
                    "possible from it -- use --keep-profiles to keep the template's running surface "
                    "with the model's mileage layout, or supply a model whose two rails both carry "
                    "section tables. "
                    if gauge["other_side_stations"] < 3 else
                    "Import both sides in one go, or pass --allow-gauge-change to say you mean it. "
                )
                + "Pass --allow-gauge-change only if you mean to change the gauge.",
                detail={
                    "code": "lateral_gauge_change",
                    "gauge_mm": round(float(gauge["gauge_mm"]), 3),
                    "this_side_mm": round(float(gauge["signed_mm"]), 3),
                    "other_side_mm": round(float(gauge["other_side_mm"]), 3),
                    "other_side_stations": int(gauge["other_side_stations"]),
                    "at_m": round(float(gauge["at_m"]), 3),
                    "limit_mm": LATERAL_GAUGE_LIMIT_MM,
                    "both_sides_possible": bool(gauge["other_side_stations"] >= 3),
                    "ways_out": ["--keep-profiles", "--allow-gauge-change", "a model with both rails"],
                })

    new_stations = []
    for entry, path in zip(chosen, source_files):
        profile = _template_profile(profile_template, path)
        if import_lateral and not keep_profiles:
            delta = _crown_lateral_delta(entry, profile_template)
            if delta is not None:
                profile["y_offset_m"] = round(float(profile.get("y_offset_m", 0.0)) + delta, 9)
                profile["y_offset_from"] = "simpack crown"
                lateral.append((abs(delta), entry.station_m))
        new_stations.append({
            "id": f"SP{entry.index:03d}",
            "s_m": round(entry.station_m + shift, 6),
            "profile": profile,
        })
    target["stations"] = new_stations

    run = dict(template.get("run") or {})
    run["x_start_m"] = float(x_start_m)
    if duration_s is not None:
        if duration_s <= 0:
            raise SimpackCaseError(f"duration_s must be positive, got {duration_s}")
        run["duration_s"] = float(duration_s)
    template["run"] = run
    template["case_id"] = case_id or f"simpack_{side}_{Path(template_file).stem}"
    # ``purpose`` is a closed vocabulary in VehicleCase (synthetic | engineering); a Simpack-derived
    # case is still an engineering case — the difference lives in ``purpose_detail`` and the sidecar.
    template["purpose"] = "engineering"
    if not template.get("parameter_source"):
        raise SimpackCaseError(f"{template_file} has no parameter_source to inherit")
    template["purpose_detail"] = (
        f"rail geometry from {catalog.get('model')} (side {side}); physics from "
        f"{template_file.name}. Generated by velch simpack-case.")

    out = Path(out_path)
    if out.suffix.lower() != ".json":
        raise SimpackCaseError(f"out_path must end with .json, got {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")

    sidecar = out.with_suffix(".simpack.json")
    sidecar.write_text(json.dumps({
        "schema_version": SCHEMA_VERSION,
        "catalog": str(catalog_file),
        "catalog_sha256": _sha256(catalog_file),
        "simpack_model": catalog.get("model"),
        "simpack_model_root": catalog.get("model_root"),
        "profile_set_sha256": (catalog.get("summary") or {}).get("profile_set_sha256"),
        "template": str(template_file),
        "template_sha256": _sha256(template_file),
        "case": str(out),
        "case_sha256": _sha256(out),
        "side": side,
        "rail": rail,
        "shift_m": round(shift, 6),
        "model_mileage_span_m": [round(span_lo, 6), round(span_hi, 6)],
        "x_start_m": float(x_start_m),
        "duration_s": run.get("duration_s"),
        "station_count": len(new_stations),
        "lateral_gauge_mm": gauge,
        "crown_lateral_m": (None if not lateral else {
            "max_abs": round(max(item[0] for item in lateral), 4),
            "at_m": round(max(lateral, key=lambda item: item[0])[1], 3),
            "shifted_stations": len(lateral)}),
        "crown_delta_mm": (None if crowns is None
                           else {"max_abs": round(crowns[0], 3), "at_m": round(crowns[1], 3),
                                 "max_lateral_m": round(crowns[2], 4),
                                 "measured_stations": len(in_window or chosen),
                                 "ride_window_m": [round(park_lo, 3), round(park_hi, 3)]}),
        "crown_warning": warning,

        "dropped_duplicate_stations": dropped,
        "stations": [
            {"s_m": entry["s_m"], "profile": entry["profile"]["file"],
             "catalog_sha256": source.sha256}
            for entry, source in zip(new_stations, chosen)
        ],
        "from_simpack": (["station mileage", "rail side", "station count"] if keep_profiles
                         else ["rail profile file", "station mileage", "rail side"]),
        "profiles_from": "template" if keep_profiles else "simpack",
        "from_template": ["vehicle", "contact", "wheels", "track_dynamics",
                          "equilibrate_vertical", "run"],
        "simpack_dynamics_imported": False,
        "not_imported": ["rigid body dynamics", "flexible (modal) track", "solver settings",
                         "measured or reference results"],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    return CaseBuild(
        case_path=out,
        sidecar_path=sidecar,
        station_count=len(new_stations),
        dropped_duplicates=dropped,
        shift_m=shift,
        profile_set_sha256=str((catalog.get("summary") or {}).get("profile_set_sha256")),
        template=str(template_file),
        model=str(catalog.get("model")),
        profiles_from="template" if keep_profiles else "simpack",
        crown_delta_mm=(None if crowns is None else {
            "max_abs": round(crowns[0], 3), "at_m": round(crowns[1], 3),
            "max_lateral_m": round(crowns[2], 4)}),
        crown_warning=warning,
    )


def describe(catalog: dict[str, Any]) -> dict[str, Any]:
    """A short, quotable digest of what the catalog found — used by the CLI and the docs."""

    summary = dict(catalog.get("summary") or {})
    rails: dict[str, int] = {}
    for entry in catalog.get("profile_references") or []:
        key = f"{entry.get('rail')}:{entry.get('side')}"
        rails[key] = rails.get(key, 0) + 1
    mileages = [float(entry.get("station_m", 0.0))
                for entry in catalog.get("profile_references") or []]
    summary["rails"] = rails
    if mileages:
        summary["mileage_span_m"] = [round(min(mileages), 3), round(max(mileages), 3)]
    return summary
