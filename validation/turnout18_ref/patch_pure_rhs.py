"""Make the right-hand side a pure function for implicit integrators.

Patch script (the harness's PowerShell mangles inline Python containing quotes).
"""

from pathlib import Path

PATH = Path(__file__).resolve().parents[2] / "src" / "velch" / "vehicle_solver.py"

HELPER = '''    def snapshot_contact_state(self) -> dict[str, object]:
        """Copy the cross-call contact memory so a solve step can be replayed."""
        return {
            "seed": dict(self._contact_seed),
            "age": dict(self._contact_age),
            "active": dict(self._active_body),
        }

    def restore_contact_state(self, snapshot: dict[str, object]) -> None:
        self._contact_seed = dict(snapshot["seed"])  # type: ignore[arg-type]
        self._contact_age = dict(snapshot["age"])  # type: ignore[arg-type]
        self._active_body = dict(snapshot["active"])  # type: ignore[arg-type]

    def derivative_pure(self, t_s: float, state: np.ndarray) -> np.ndarray:
        """Right-hand side with the contact memory discarded after the call.

        Explicit integrators evaluate the right-hand side once per step, so the
        seed and hysteresis memory is a one-way recursion along the trajectory.
        Implicit integrators evaluate it many times at neighbouring states of the
        same step; keeping the memory in place makes those evaluations overwrite
        each other and the map stops being a function of the state. Restoring the
        memory after each call makes it a pure function without changing the
        single-call physics.
        """
        snapshot = self.snapshot_contact_state()
        try:
            return self.derivative(t_s, state)
        finally:
            self.restore_contact_state(snapshot)

'''

ANCHOR = "    def mechanical_energy_j("
OLD = "    solution = solve_ivp(dynamics.derivative, (0, run.duration_s), initial,"
NEW = (
    '    rhs = dynamics.derivative_pure if run.method in {"BDF", "Radau"} '
    "else dynamics.derivative\n"
    "    solution = solve_ivp(rhs, (0, run.duration_s), initial,"
)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    if "def derivative_pure" in text and OLD not in text:
        # Already applied (2026-10-21: the helper has since been extended to five
        # snapshot keys and the sparsity probe moved to derivative_pure; this
        # script must not try to re-insert the first version).
        print("already applied:", PATH)
        return 0
    if "def derivative_pure" not in text:
        assert ANCHOR in text
        text = text.replace(ANCHOR, HELPER + ANCHOR, 1)
    assert OLD in text
    text = text.replace(OLD, NEW, 1)
    PATH.write_text(text, encoding="utf-8")
    print("patched", PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
