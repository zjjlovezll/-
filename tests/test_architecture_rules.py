"""Architecture fitness functions: import direction is a test, not a convention.

The rules here encode the layering argued for in ``docs/ARCHITECTURE_2026-10-21.md``:

    ui / gui  ->  cli  ->  vehicle_solver  ->  {vehicle, track_models, contact, jacobian}
                        ->  metrics / io / inverse      (read-only, downstream)
    case.spec -> vehicle                              (contract only, never the solver)

``inverse`` is the analysis layer.  It may read a saved history table and it must
never be reachable from the forward solver, because a forward run has to stay
reproducible without the inverse package installed.  Only two readers are
tolerated, each in a narrow shape, and both are named explicitly below so a third
edge fails the suite instead of quietly widening the seam:

* :mod:`velch.io.measured` borrows the ``channels``/``observation`` contracts
  (measured data arrives as observations);
* the presentation layer borrows ``inverse.bands`` only -- a pure spectrum helper
  used to draw a band table, not an estimator.

Everything is a static AST scan, so the rules hold even when a module cannot be
imported on the current box (no display, no CONTACT DLL, no h5py).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "velch"

#: Modules that compute or orchestrate forward dynamics.
FORWARD = frozenset(
    {
        "velch.contact",
        "velch.contact_geometry",
        "velch.contact_law",
        "velch.contact_native",
        "velch.jacobian",
        "velch.model",
        "velch.profiles",
        "velch.simpack_track_import",
        "velch.solver",
        "velch.support_compliance",
        "velch.track_models",
        "velch.vehicle",
        "velch.vehicle_solver",
    }
)

#: Modules that drive a forward run (a case file must not reach any of these).
SOLVER_SIDE = FORWARD | frozenset({"velch.cli", "velch.metrics", "velch.parallel"})

#: Presentation modules: they may validate a case, read artifacts, and plot.
PRESENTATION = frozenset({"velch.gui", "velch.gui_support", "velch.ui"})

#: What presentation code is allowed to reach.  ``profiles`` is here because
#: drawing a wheel/rail profile needs the same series the solver samples -- it is
#: a geometry reader, not a dynamics module, so no numeric path is duplicated.
PRESENTATION_MAY_IMPORT = PRESENTATION | frozenset(
    {
        "velch.model",
        "velch.vehicle",
        "velch.profiles",
        "velch.metrics",
        "velch.io",
        "velch.io.history",
        "velch.case",
        "velch.case.spec",
        "velch.inverse.bands",
    }
)

#: ``inverse`` is the analysis layer.  It may read a saved history table and it must


@dataclass(frozen=True, order=True)
class Edge:
    """One intra-package import: ``module`` imports ``imported`` at ``line``.

    ``kind`` is how the import actually arrives:

    * ``runtime``  -- module/class level, executes on ``import``;
    * ``deferred`` -- inside a function body, executes on first call;
    * ``typing``   -- inside ``if TYPE_CHECKING:``, never executes at all.

    The package already uses both non-runtime forms on purpose
    (``io/measured.py`` -> ``inverse`` under ``TYPE_CHECKING``, ``ui/__init__`` ->
    ``ui.app``, ``vehicle_solver`` -> ``jacobian``).  Direction rules treat all
    three as real dependencies -- a type-level import in the wrong direction is
    still the wrong direction -- while the cycle rule looks at ``runtime`` only.
    """

    module: str
    imported: str
    line: int
    kind: str = "runtime"


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(SRC).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(["velch", *parts]) if parts else "velch"


def _resolve(module: str, node: ast.ImportFrom, *, is_package: bool) -> str | None:
    """Absolute module name a relative ``from ... import`` points at."""

    if node.level == 0:
        return node.module
    parts = module.split(".")
    if not is_package:
        parts = parts[:-1]  # the package that contains this module
    drop = node.level - 1
    if drop >= len(parts) + 1:
        return None
    if drop:
        parts = parts[:-drop]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def _is_type_checking(test: ast.expr) -> bool:
    """``if TYPE_CHECKING:`` / ``if typing.TYPE_CHECKING:`` in any spelling."""

    node: ast.expr = test
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name) and node.id == "TYPE_CHECKING"


def _scan(
    body: list[ast.stmt],
    module: str,
    *,
    is_package: bool,
    kind: str,
    out: set[Edge],
) -> None:
    """Collect import edges, remembering how each one arrives."""

    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _scan(node.body, module, is_package=is_package, kind="deferred", out=out)
            continue
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            _scan(node.body, module, is_package=is_package, kind="typing", out=out)
            continue
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            names = (
                [_resolve(module, node, is_package=is_package)]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
            )
            for name in names:
                if name and name.startswith("velch"):
                    out.add(Edge(module, name, node.lineno, kind))
            continue
        # Class bodies, ``if``/``try``/``with`` blocks all execute at import time.
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ExceptHandler):
                _scan(child.body, module, is_package=is_package, kind=kind, out=out)
            elif isinstance(child, ast.stmt):
                _scan([child], module, is_package=is_package, kind=kind, out=out)


def _edges() -> tuple[set[Edge], dict[str, Path]]:
    """All intra-package import edges plus the module -> file map."""

    files = {_module_name(path): path for path in sorted(SRC.rglob("*.py"))}
    edges: set[Edge] = set()
    for module, path in files.items():
        is_package = path.name == "__init__.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        _scan(tree.body, module, is_package=is_package, kind="runtime", out=edges)
    return edges, files


EDGES, FILES = _edges()


def _importers_of(prefixes: tuple[str, ...]) -> set[Edge]:
    return {
        edge
        for edge in EDGES
        if any(edge.imported == p or edge.imported.startswith(p + ".") for p in prefixes)
    }


def _format(edges: set[Edge]) -> str:
    return "\n".join(f"{e.module}:{e.line} -> {e.imported}" for e in sorted(edges))


def test_src_tree_is_populated() -> None:
    """Guard against the scan silently passing on an empty/wrong path."""

    assert "velch.vehicle_solver" in FILES
    assert "velch.inverse.estimator" in FILES
    assert len(EDGES) > 30


def test_inverse_is_never_reached_from_forward_code() -> None:
    """No forward, driver, or case module may import the analysis layer."""

    forbidden = SOLVER_SIDE | {"velch.case", "velch.case.spec"}
    offenders = {
        edge
        for edge in _importers_of(("velch.inverse",))
        if not edge.module.startswith("velch.inverse") and edge.module in forbidden
    }
    assert not offenders, (
        "forward code must not import inverse/*; a run has to stay reproducible "
        "without the analysis layer:\n" + _format(offenders)
    )


def test_only_the_data_layer_and_presentation_read_inverse() -> None:
    """Reading analysis output is allowed in exactly two narrow shapes."""

    readers = {
        edge
        for edge in _importers_of(("velch.inverse",))
        if not edge.module.startswith("velch.inverse")
    }
    measured = {e for e in readers if e.module == "velch.io.measured"}
    assert measured, "io.measured no longer imports inverse/*; tighten this rule"
    assert all(
        e.imported in {"velch.inverse.channels", "velch.inverse.observation"} for e in measured
    ), "io.measured may only borrow the channels/observation contracts:\n" + _format(measured)

    shown = {e for e in readers - measured if not e.module.startswith("velch.ui")}
    assert not shown, "unexpected importer of inverse/*:\n" + _format(shown)
    plotted = {e for e in readers - measured}
    assert all(e.imported == "velch.inverse.bands" for e in plotted), (
        "presentation may only borrow the band table helper (a pure spectrum "
        "utility), not estimators or contracts:\n" + _format(plotted)
    )


def test_inverse_does_not_import_the_forward_solver() -> None:
    """The analysis layer reads tables; it never pulls in dynamics."""

    offenders = {
        e for e in EDGES if e.module.startswith("velch.inverse.") and e.imported in SOLVER_SIDE
    }
    assert not offenders, "inverse/* must not import forward modules:\n" + _format(offenders)


def test_contact_layer_does_not_import_its_callers() -> None:
    """``contact`` is a leaf of the forward graph: callers depend on it, not vice versa."""

    banned = FORWARD | frozenset({"velch.cli", "velch.metrics", "velch.parallel"})
    # ``contact_geometry`` is a leaf primitive like ``profiles`` or ``contact_law``:
    # it imports nothing from the project, so a geometry backend depending on it is a
    # peer dependency, not an upward one.
    banned = banned - {"velch.contact", "velch.contact_law", "velch.profiles",
                       "velch.support_compliance", "velch.contact_geometry"}
    offenders = {
        e
        for e in EDGES
        if e.module.startswith("velch.contact") and e.imported in banned
    }
    assert not offenders, "contact* must stay below its callers:\n" + _format(offenders)


def test_case_spec_only_touches_the_vehicle_contract() -> None:
    """A case file names parameters; it must not reach a solver or an estimator."""

    allowed = {"velch.vehicle", "velch.case", "velch.case.spec"}
    offenders = {
        e
        for e in EDGES
        if e.module.startswith("velch.case") and e.imported not in allowed
    }
    assert not offenders, "case/* may only import the vehicle contract:\n" + _format(offenders)
    assert any(e.imported == "velch.vehicle" for e in EDGES if e.module == "velch.case.spec")


def test_history_table_is_a_leaf_module() -> None:
    """``io.history`` currently imports no Velch module; that is what keeps the cycle alive."""

    offenders = {e for e in EDGES if e.module == "velch.io.history"}
    assert not offenders, "io.history must stay a leaf:\n" + _format(offenders)


def test_contract_modules_do_not_import_the_implementation() -> None:
    """``model``/``vehicle``/``track_models`` describe the problem; they must not solve it."""

    contracts = ("velch.model", "velch.vehicle", "velch.track_models", "velch.support_compliance")
    banned = frozenset({"velch.vehicle_solver", "velch.solver", "velch.parallel", "velch.cli"})
    offenders = {
        e for e in EDGES if e.module in contracts and e.imported in banned
    }
    assert not offenders, "contract modules must not import the solver:\n" + _format(offenders)


def test_vehicle_solver_borrows_only_the_exception_from_v1() -> None:
    """v2 must not accidentally inherit the v1 ``simulate`` orchestration."""

    path = FILES["velch.vehicle_solver"]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    borrowed: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        target = _resolve("velch.vehicle_solver", node, is_package=False)
        if target == "velch.solver":
            borrowed.update(alias.name for alias in node.names)
    assert borrowed == {"SimulationFailure"}, (
        "vehicle_solver should borrow only SimulationFailure from solver.py, got "
        f"{sorted(borrowed)}"
    )


def _source_line(module: str, line: int) -> str:
    """The raw source text of one line, used to vet individual import edges."""

    text = FILES[module].read_text(encoding="utf-8").splitlines()
    return text[line - 1].strip() if 0 < line <= len(text) else ""


def test_presentation_does_not_import_the_forward_stack() -> None:
    """GUI/UI may validate a case and read artifacts; numerics go through the CLI."""

    def allowed(edge: Edge) -> bool:
        if edge.imported.startswith("velch.ui"):
            return True
        if edge.imported in PRESENTATION_MAY_IMPORT:
            return True
        # The package root only carries ``__version__``; nothing else may be
        # pulled from it, so the edge is vetted line by line.
        return (
            edge.imported == "velch"
            and edge.kind != "runtime"
            and _source_line(edge.module, edge.line) == "from velch import __version__"
        )

    offenders = {
        e
        for e in EDGES
        if (e.module.split(".")[-1] in {"gui", "gui_support"} or e.module.startswith("velch.ui"))
        if not allowed(e)
    }
    assert not offenders, (
        "presentation code must not import the forward stack directly:\n" + _format(offenders)
    )


def test_no_import_time_cycle() -> None:
    """The import-time module graph is a DAG.

    Only ``runtime`` edges count.  Function-body imports (``deferred``) and
    ``if TYPE_CHECKING:`` imports (``typing``) never execute during ``import``,
    and this package uses both on purpose to keep
    ``ui -> app -> screen -> ui``, ``vehicle_solver -> jacobian -> contact`` and
    ``io.measured -> inverse`` acyclic.
    """

    graph: dict[str, set[str]] = {}
    for edge in EDGES:
        if edge.kind != "runtime":
            continue
        graph.setdefault(edge.module, set()).add(edge.imported)

    colour: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[str] = []

    def visit(node: str) -> None:
        colour[node] = 1
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            state = colour.get(nxt, 0)
            if state == 0:
                visit(nxt)
            elif state == 1:
                start = stack.index(nxt)
                cycles.append(" -> ".join([*stack[start:], nxt]))
        stack.pop()
        colour[node] = 2

    for node in sorted(graph):
        if colour.get(node, 0) == 0:
            visit(node)
    assert not cycles, "intra-package import cycle(s):\n" + "\n".join(cycles)


def test_io_measured_touches_inverse_only_below_run_time() -> None:
    """The data layer may name the analysis layer in types, never at import time.

    ``velch.io.measured`` is the one place where the dependency direction is
    inverted: it annotates with ``inverse.channels``/``inverse.observation``
    types (``io/measured.py`` under ``if TYPE_CHECKING:``) and calls into them
    from function bodies.  Both forms are deliberate cycle breaks, and this test
    pins them: if one of those imports is promoted to module level,
    ``import velch.io`` gains a hard runtime dependency on the whole analysis
    package and the cycle comes back.
    """

    edges = [edge for edge in EDGES if edge.module == "velch.io.measured"]
    assert edges, "io.measured should still depend on the analysis layer somewhere"
    offenders = [edge for edge in edges if edge.kind == "runtime"]
    assert not offenders, (
        "velch/io/measured.py must reach velch.inverse only from a function body or "
        "under `if TYPE_CHECKING:`:\n" + _format(offenders)
    )


@pytest.mark.parametrize("module", ["velch.inverse", "velch.io", "velch.case.spec", "velch.metrics"])
def test_downstream_packages_import_headless(module: str) -> None:
    """The analysis/data layer must not need a display or a solver import to load."""

    import importlib

    importlib.import_module(module)
