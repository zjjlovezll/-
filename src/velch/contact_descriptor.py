"""Per-station contact descriptor (B4).

The contact search only ever finds points on the **upper convex hull** of the rail
cross-section (for a convex wheel approached from above).  A station profile with
~500 nodes therefore carries at most a handful of candidate contact points:
vertices plus the segment that holds the minimum gap.

This module compresses one station profile to that hull and evaluates the deepest
penetration from it.  It is deliberately *lossy* where the profile is concave
(a flangeway, a seat cut): the hull bridges the groove, so the reported depth is
larger than the true surface depth.  ``describe()`` reports the gap so callers can
gate on it instead of guessing.

Prices are measured, not assumed: see ``validation/crh380a_m/probe_descriptor.py``
and ``docs/B4_DESCRIPTOR_2026-10-22.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["ContactDescriptor", "upper_hull_indices"]


def upper_hull_indices(
    y_m: np.ndarray, z_m: np.ndarray, *, tolerance_m: float = 1.0e-6
) -> np.ndarray:
    """Indices of the upper convex hull vertices, y increasing.

    Monotone chain: keep the chain while it turns clockwise (concave down), pop
    while it turns counter-clockwise or is within ``tolerance_m`` of the current
    segment.  The tolerance matters: a discretised measured profile has thousands
    of sub-micrometre wiggles, and without it the "hull" keeps nearly every node
    and compresses nothing.
    """
    y = np.asarray(y_m, dtype=float)
    z = np.asarray(z_m, dtype=float)
    if y.size != z.size:
        raise ValueError("y and z must have the same length")
    if y.size < 3:
        return np.arange(y.size)

    order = np.argsort(y, kind="stable")
    y = y[order]
    z = z[order]

    hull: list[int] = []
    for index in range(y.size):
        while len(hull) >= 2:
            first, second = hull[-2], hull[-1]
            dy_segment = y[second] - y[first]
            dz_segment = z[second] - z[first]
            length = float(np.hypot(dy_segment, dz_segment))
            if length <= 0.0:
                hull.pop()
                continue
            cross = dy_segment * (z[index] - z[first]) - dz_segment * (
                y[index] - y[first]
            )
            if cross / length >= -tolerance_m:
                hull.pop()
            else:
                break
        hull.append(index)
    return order[np.asarray(hull, dtype=int)]


@dataclass(frozen=True)
class ContactDescriptor:
    """Upper-hull compression of one rail cross-section."""

    y_m: np.ndarray
    z_m: np.ndarray
    slope: np.ndarray
    source_nodes: int
    hull_nodes: int
    bridge_depth_m: float
    span_m: float

    @classmethod
    def build(cls, y_m: np.ndarray, z_m: np.ndarray) -> "ContactDescriptor":
        y = np.asarray(y_m, dtype=float)
        z = np.asarray(z_m, dtype=float)
        if y.size != z.size:
            raise ValueError("y and z must have the same length")
        index = upper_hull_indices(y, z)
        hull_y = y[index]
        hull_z = z[index]

        slope = np.zeros(max(hull_y.size - 1, 1), dtype=float)
        if hull_y.size >= 2:
            span = np.diff(hull_y)
            span = np.where(span == 0.0, 1.0, span)
            slope = np.diff(hull_z) / span

        # Largest amount by which the hull lies above the real surface.
        bridge = 0.0
        if hull_y.size >= 2 and y.size:
            hull_on_nodes = np.interp(y, hull_y, hull_z)
            bridge = float(np.max(hull_on_nodes - z))

        return cls(
            y_m=hull_y,
            z_m=hull_z,
            slope=slope,
            source_nodes=int(y.size),
            hull_nodes=int(hull_y.size),
            bridge_depth_m=bridge,
            span_m=float(hull_y[-1] - hull_y[0]) if hull_y.size else 0.0,
        )

    # -- evaluation -----------------------------------------------------
    def rail_z_at(self, y_m) -> np.ndarray:
        return np.interp(np.asarray(y_m, dtype=float), self.y_m, self.z_m)

    def deepest(self, wheel_y_m, wheel_z_m, *, samples_per_segment: int = 8):
        """Deepest hull penetration for one wheel pose.

        Vectorised: all hull segments are sampled in one broadcast, so the cost is
        a handful of numpy calls on a few hundred elements.  A Python loop over
        segments is ~15x slower on the same data (measured, see the B4 doc) and is
        what makes a "coarse" descriptor paradoxically slower than the fine grid.

        Parameters
        ----------
        wheel_y_m, wheel_z_m:
            Wheel surface samples in the common frame (metres), sorted by y.
        samples_per_segment:
            The hull is piecewise linear; the wheel is curved, so the gap minimum
            on a segment is interior.

        Returns ``(depth_m, y_m, rail_z_m, wheel_z_m, slope)``; all zeros with
        ``y_m`` = NaN when nothing penetrates.
        """
        empty = (0.0, float("nan"), 0.0, 0.0, 0.0)
        wy = np.asarray(wheel_y_m, dtype=float)
        wz = np.asarray(wheel_z_m, dtype=float)
        if wy.size < 2 or self.y_m.size < 2:
            return empty

        lower = max(float(wy[0]), float(self.y_m[0]))
        upper = min(float(wy[-1]), float(self.y_m[-1]))
        if not upper > lower:
            return empty

        y0 = self.y_m[:-1]
        y1 = self.y_m[1:]
        keep = (y1 > lower) & (y0 < upper)
        if not np.any(keep):
            return empty

        y0 = np.maximum(y0[keep], lower)
        y1 = np.minimum(y1[keep], upper)
        valid = y1 > y0
        if not np.any(valid):
            return empty
        y0 = y0[valid]
        y1 = y1[valid]
        z0 = self.z_m[:-1][keep][valid]
        z1 = self.z_m[1:][keep][valid]
        slope = self.slope[keep][valid]

        pieces = max(1, int(samples_per_segment))
        fraction = np.linspace(0.0, 1.0, pieces + 1)
        grid = (y0[:, None] + (y1 - y0)[:, None] * fraction[None, :]).ravel()
        grid = np.unique(grid)

        rail_z = np.interp(grid, self.y_m, self.z_m)
        rail_slope = np.interp(
            grid, self.y_m[:-1], self.slope, left=self.slope[0], right=self.slope[-1]
        )
        wheel_z = np.interp(grid, wy, wz)
        inv = 1.0 / np.sqrt(1.0 + rail_slope * rail_slope)
        depth = (rail_z - wheel_z) * inv
        best = int(np.argmax(depth))
        value = float(depth[best])
        if not value > 0.0:
            return empty
        return (
            value,
            float(grid[best]),
            float(rail_z[best]),
            float(wheel_z[best]),
            float(rail_slope[best]),
        )

    def _segment_bounds(self, lower: float, upper: float) -> tuple[float, float]:
        return lower, upper

    def describe(self) -> dict:
        return {
            "source_nodes": self.source_nodes,
            "hull_nodes": self.hull_nodes,
            "compression": (
                float(self.source_nodes) / float(self.hull_nodes)
                if self.hull_nodes
                else float("inf")
            ),
            "bridge_depth_um": self.bridge_depth_m * 1.0e6,
            "span_mm": self.span_m * 1.0e3,
        }
