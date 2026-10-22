"""The contact layer is split into siblings; the facade must stay complete.

These assertions exist because the split is invisible to every caller: ``from velch.contact import
ContactParameters`` has to keep working forever.  A name quietly added to a sibling and forgotten
in the facade is exactly the kind of break that only shows up in a user's script, so each one is
pinned here.
"""
from __future__ import annotations

import ast
from pathlib import Path

import velch.contact as contact
import velch.contact_grid as grid
import velch.contact_models as models
import velch.contact_search as search

PUBLIC = (
    "GEOMETRY_POLICIES",
    "CURVATURE_POLICIES",
    "NORMAL_POLICIES",
    "STRIP_CENTER_POLICIES",
    "DAMPING_POLICIES",
    "POINT_POLICIES",
    "STIFFNESS_POLICIES",
    "ContactParameters",
    "ContactPartials",
    "ContactGeometry",
    "ContactResponse",
    "merge_contact_responses",
    "deduplicate_contacts",
    "find_patch_contact",
    "find_strip_contact",
    "find_spline_contact",
    "find_graph_contact",
    "find_graph_contacts",
    "evaluate_contact",
    "saturate_creep_force",
    "hunt_crossley_coefficient",
    "series_normal_force",
)

PRIVATE = ("_contact_on_span", "_absolute_arrays", "_build_rail_grid", "_rail_grid_cache")

SIBLINGS = (models, grid, search)


def _imported_modules(module) -> set[str]:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            if node.level:
                found.add("." * node.level + node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
    return found


def _defined_here(module) -> set[str]:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }


def test_the_facade_reexports_every_documented_name() -> None:
    missing = [name for name in PUBLIC if not hasattr(contact, name)]
    assert not missing, f"velch.contact lost these names: {missing}"


def test_the_names_a_test_reaches_into_survive_too() -> None:
    missing = [name for name in PRIVATE if not hasattr(contact, name)]
    assert not missing, f"velch.contact lost these private names: {missing}"


def test_each_home_owns_what_it_claims() -> None:
    """Where a thing lives is part of the design, not an implementation accident."""

    assert models.ContactParameters is contact.ContactParameters
    assert models.ContactResponse is contact.ContactResponse
    assert models.merge_contact_responses is contact.merge_contact_responses
    assert grid._build_rail_grid is contact._build_rail_grid
    assert search.find_strip_contact is contact.find_strip_contact
    assert search._contact_on_span is contact._contact_on_span
    assert contact.find_graph_contact.__module__ == "velch.contact"
    assert contact.evaluate_contact.__module__ == "velch.contact"


def test_the_heavy_searches_no_longer_live_in_the_facade() -> None:
    """The split's whole point: the facade orchestrates, it does not search."""

    defined = _defined_here(contact)
    assert {"find_graph_contact", "evaluate_contact", "saturate_creep_force"} <= defined
    assert not {"find_strip_contact", "find_patch_contact", "find_spline_contact",
                "_contact_on_span"} & defined
    assert "_contact_on_span" in _defined_here(search)


def test_the_siblings_do_not_import_the_facade() -> None:
    """``contact`` re-exports its siblings; the siblings must not depend back on it."""

    for module in SIBLINGS:
        imported = _imported_modules(module)
        assert not {".contact", "velch.contact", "..contact"} & imported, (
            f"{module.__name__} imports the facade: {sorted(imported)}"
        )


def test_the_siblings_stay_inside_the_contact_leaf() -> None:
    """Mirrors the architecture rule for the new modules at their own level."""

    allowed_prefixes = (
        ".contact_law", ".contact_models", ".contact_grid", ".contact_search",
        ".profiles", ".support_compliance", ".contact_geometry",
    )
    for module in SIBLINGS:
        for name in _imported_modules(module):
            if not name.startswith("."):
                continue
            assert name.startswith(allowed_prefixes), (
                f"{module.__name__} imports {name}, which is above the contact leaf"
            )
