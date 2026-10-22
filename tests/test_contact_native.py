"""Guard against reporting a simplified force as a CONTACT result."""
from __future__ import annotations

import pytest

import velch.contact_native as native
from velch.contact_native import (ContactNativeUnavailable, HertzProbe, assess_spherical_hertz_probe,
                                  inspect_contact_native, run_contact_hertz_probe)


def test_missing_binary_is_explicit_failure(tmp_path):
    interface = tmp_path / "python_intfc" / "__init__.py"
    interface.parent.mkdir()
    interface.write_text("", encoding="utf-8")
    status = inspect_contact_native(tmp_path)
    assert status["interface_present"] is True
    assert status["binary_present"] is False
    assert status["ready_to_attempt_native_load"] is False

    probe = HertzProbe(1.0, 1.0, 1e-4, 10.0, 2.1e11, 0.3, 0.3, 0.001, 0.0)
    with pytest.raises(ContactNativeUnavailable, match="contact_addon"):
        run_contact_hertz_probe(tmp_path, probe)


def test_probe_rejects_nonphysical_units():
    with pytest.raises(ValueError, match="positive SI"):
        HertzProbe(0.0, 1.0, 1e-4, 10.0, 2.1e11, 0.3, 0.3, 0.0, 0.0)


def test_native_boundary_converts_si_to_contact_units(monkeypatch, tmp_path):
    class RecordingContact:
        def __init__(self):
            self.calls = {}

        def initlibrary(self, *_args):
            return ({"if_units": 1, "if_wrtinp": 2, "ic_matfil": 3,
                     "ic_output": 4, "ic_flow": 5, "ic_norm": 6,
                     "ic_tang": 7, "ic_pvtime": 8, "un_cntc": 9}, 2601, 0)

        def initialize(self, *_args, **_kwargs):
            return (2601, 0)

        def __getattr__(self, name):
            def record(*args):
                self.calls[name] = args
                if name == "calculate":
                    return 0
                if name == "getcontactforces":
                    return (1000.0, -10.0, 2.0, 500.0)
                if name == "getcontactpatchareas":
                    return (10.0, 8.0, 2.0, 0.0)
            return record

    fake = RecordingContact()
    monkeypatch.setattr(native, "_load_contact", lambda _root: fake)
    monkeypatch.setattr(native, "inspect_contact_native", lambda _root: {"binary_sha256": "test"})
    probe = HertzProbe(1.0, 2.0, 1e-4, 10.0, 2.1e11, 0.3, 0.3, 0.001, -0.002, 0.01)
    result = run_contact_hertz_probe(tmp_path, probe, grid_n=32)
    assert fake.calls["sethertzcontact"][3][2:4] == [0.001, 0.002]
    assert fake.calls["setpenetration"][2] == pytest.approx(0.1)
    assert fake.calls["setreferencevelocity"][2] == pytest.approx(10000.0)
    assert fake.calls["setcreepages"][4] == pytest.approx(1e-5)
    assert result["spin_moment_nm"] == pytest.approx(0.5)
    assert result["patch_area_m2"] == pytest.approx(1e-5)


def test_spherical_reference_checks_native_force_and_friction_limit():
    probe = HertzProbe(1 / 0.92, 1 / 0.92, 1e-4, 10.0, 2.1e11, 0.3, 0.3, 0.001, 0.0)
    result = {"normal_force_n": 104352.208920593, "tangent_x_n": -13778.5191046669,
              "tangent_y_n": 0.0, "patch_area_m2": 0.00014619375}
    check = assess_spherical_hertz_probe(probe, [result])
    assert check["expected_normal_force_n"] == pytest.approx(104343.53820192722)
    assert check["finest_grid_normal_force_relative_error"] < 1e-4
    assert check["coulomb_bound_satisfied_all_grids"] is True
