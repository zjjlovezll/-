import pathlib, re

# ---------- contact.py : add multi-contact search ----------
p = pathlib.Path("src/velch/contact.py")
s = p.read_text(encoding="utf-8")
if "def find_graph_contacts" in s:
    print("contact.py already patched")
else:
    code = '''

def find_graph_contacts(
    wheel_profile: GraphProfile,
    rail_sample: ProfileSample,
    *,
    wheel_y_m: float,
    wheel_z_m: float,
    wheel_roll_rad: float,
    wheel_lateral_offset_m: float,
    rail_y_m: float,
    rail_z_m: float,
    maximum_contacts: int = 3,
    minimum_separation_m: float = 0.004,
) -> tuple[ContactGeometry, ...]:
    """Return every local maximum of the vertical graph gap on one rail patch.

    A turnout cross-section merges the stock, switch and wing rail heads into a
    single z(y) polyline, so the depth surface carries several local maxima. The
    single-contact search keeps only the deepest one and jumps between rail heads;
    this search keeps one contact per lobe so each rail head carries its own load.
    Lobes closer than ``minimum_separation_m`` are treated as one contact.
    """
    local_y = wheel_lateral_offset_m + wheel_profile.y_m
    local_z = wheel_profile.z_m
    c, s = math.cos(wheel_roll_rad), math.sin(wheel_roll_rad)
    wheel_y = wheel_y_m + c * local_y - s * local_z
    wheel_z = wheel_z_m + s * local_y + c * local_z
    if not bool(np.all(wheel_y[1:] > wheel_y[:-1])):
        raise ValueError("wheel roll made the lower envelope non-monotonic in lateral y")
    rail_y = rail_y_m + rail_sample.profile.y_m
    rail_z = rail_z_m + rail_sample.profile.z_m
    lower, upper = max(wheel_y[0], rail_y[0]), min(wheel_y[-1], rail_y[-1])
    if upper <= lower:
        return ()
    grid = _merge_grid(wheel_y, rail_y, lower, upper)
    if grid.size < 3:
        return ()
    w_z = np.interp(grid, wheel_y, wheel_z)
    r_z = np.interp(grid, rail_y, rail_z)
    slopes = _grid_slope(r_z, grid)
    inv_lengths = 1.0 / np.sqrt(1.0 + slopes * slopes)
    depth = (r_z - w_z) * inv_lengths
    inner = depth[1:-1]
    peaks = np.flatnonzero((inner >= depth[:-2]) & (inner > depth[2:])) + 1
    candidates = [int(i) for i in peaks if depth[i] > 0.0]
    if not candidates:
        return ()
    candidates.sort(key=lambda i: -depth[i])
    chosen: list[int] = []
    for i in candidates:
        if all(abs(grid[i] - grid[j]) >= minimum_separation_m for j in chosen):
            chosen.append(i)
        if len(chosen) >= maximum_contacts:
            break
    chosen.sort(key=lambda i: grid[i])
    out = []
    for i in chosen:
        y = float(grid[i])
        slope = float(slopes[i])
        inv = float(inv_lengths[i])
        dz_ds = float(np.interp(y - rail_y_m, rail_sample.profile.y_m, rail_sample.dz_ds))
        out.append(ContactGeometry(
            y_m=y,
            wheel_z_m=float(w_z[i]),
            rail_z_m=float(r_z[i]),
            penetration_m=float(depth[i]),
            normal_y=-slope * inv,
            normal_z=inv,
            tangent_y=inv,
            tangent_z=slope * inv,
            lever_y_m=y - wheel_y_m,
            lever_z_m=float(w_z[i]) - wheel_z_m,
            rail_dz_ds=dz_ds,
            edge_limited=i == 0 or i == grid.size - 1,
        ))
    return tuple(out)
'''
    p.write_text(s.rstrip() + "\n" + code, encoding="utf-8")
    print("contact.py patched (+%d lines)" % code.count("\n"))
