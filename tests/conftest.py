"""Session hooks for the test suite.

The 1.4 GB validation corpus lives outside the repository (see ``validation/INDEX.md``), so a
fresh clone has the software but not the data.  Without this hook, every module that builds a
case path at import time would fail collection, and the failure would read like twelve broken
test modules rather than one missing directory.

When the corpus is absent the whole suite is marked skipped with the resolved path in the
reason, so the report says exactly what to install and where the code looked.
"""

from __future__ import annotations

import pytest

from velch.data_root import case_dir, explain


def corpus_present() -> bool:
    """The single probe: one file that every corpus-dependent test ultimately needs."""

    return (case_dir() / "case_full12_cap05.json").is_file()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if corpus_present():
        return
    details = explain()
    reason = (
        "validation corpus not present "
        f"(looked in {details['case_dir']}, source={details['source']}); "
        "set VELCH_DATA_ROOT or add .velch-data.json -- see validation/INDEX.md"
    )
    marker = pytest.mark.skip(reason=reason)
    for item in items:
        item.add_marker(marker)
