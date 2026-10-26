"""One resolver for every file a case points at.

A case references four kinds of external file — the wheel and rail profiles, the ``.tre``
irregularity record, a modal-track file, and the flexible-wheelset mode set. Until this
module existed each one was resolved the same naive way, ``(case_dir / ref).resolve()``,
which has exactly one meaning: *relative to the case file*. That is fine inside this
repository and wrong as soon as the product is installed somewhere else, because the
mode set ships inside the package (``_internal/vehicles/modes/...``) and a relative name
in a case document cannot reach it.

So there are now four spellings, and only one of them is new:

===================================  ==========================================================
``wheel.csv``, ``sub/wheel.csv``     relative to the **case file** (unchanged, the default)
``case:sub/wheel.csv``               the same thing written out, so the meaning cannot drift
``lib:vehicles/modes/x.json``        inside the **vehicle library** — the packaged ``vehicles/``
                                     (this is where ``lib:`` matters: a shipped case must be
                                     able to name a shipped asset)
``data:crh380a_m/case_0007.json``    inside the **corpus root** (``velch.data_root``)
``F:\\...``, ``\\\\server\\...``      absolute, historical, still accepted
===================================  ==========================================================

``lib:`` deliberately reuses :func:`velch.vehicle_db.vehicle_dir` instead of inventing a
second root. The library already has to resolve source-tree / unpacked / ``_internal``
layouts, and that problem is identical here; a second root would be a second way to fail,
and the self-check would only report one of them.

Failures raise :class:`AssetRefError`, a :class:`FileNotFoundError` subclass, so existing
``except FileNotFoundError`` still works while the message says which roots were tried and
what to write instead. A bare ``FileNotFoundError`` that shows only the path it could not
open is what makes "the package is broken" and "the case was written elsewhere" look the
same.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

LIB = "lib:"
CASE = "case:"
DATA = "data:"

__all__ = ["AssetRefError", "LIB", "CASE", "DATA", "ResolvedAsset", "resolve_asset"]


class AssetRefError(FileNotFoundError):
    """A case pointed at a file that cannot be found, with the roots that were searched."""

    def __init__(self, ref: str, kind: str, reason: str, *, searched: tuple[Path, ...],
                 hint: str = "") -> None:
        self.ref = ref
        self.kind = kind
        self.reason = reason
        self.searched = tuple(searched)
        self.hint = hint
        lines = [f"cannot resolve {kind} {ref!r}: {reason}"]
        for root in self.searched:
            lines.append(f"  looked in {root}")
        if hint:
            lines.append(f"  {hint}")
        super().__init__("\n".join(lines))


@dataclass(frozen=True)
class ResolvedAsset:
    """What a reference turned into: the file, the spelling, and whether it travels."""

    ref: str
    kind: str
    path: Path
    root: Path
    portable: bool

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def _lib_root() -> Path:
    from .vehicle_db import vehicle_dir

    return vehicle_dir()


def _data_root() -> Path:
    from .data_root import data_root

    return data_root()


def _roots_for(ref: str, case_path: Path | None) -> tuple[Path, ...]:
    """Where a reference of this spelling is allowed to live, most specific first."""

    if ref.startswith(LIB):
        return (_lib_root(),)
    if ref.startswith(DATA):
        return (_data_root(),)
    if case_path is not None:
        return (case_path.resolve().parent,)
    return (Path.cwd(),)


def resolve_asset(ref: str, *, case_path: Path | None = None, kind: str = "asset") -> ResolvedAsset:
    """Turn a case reference into a file, or raise :class:`AssetRefError` naming the roots.

    ``case_path`` is the path of the **case file**, not its directory: passing the directory
    is what let the old code be wrong without ever looking wrong, so the signature asks for
    the file and takes ``.parent`` itself.
    """

    text = str(ref)
    if not text:
        raise AssetRefError(text, kind, "empty reference", searched=())
    if text.startswith(LIB):
        relative, portable, roots = text[len(LIB):], True, (_lib_root(),)
        # ``lib:`` *is* the vehicle library, so ``lib:modes/x.json`` is the short form.  A leading
        # ``vehicles/`` is accepted too, because that is how the folder appears in the source tree
        # and in the docs; rejecting it would turn a correct-looking path into a mystery.
        if relative.startswith("vehicles/"):
            relative = relative[len("vehicles/"):]
    elif text.startswith(CASE):
        relative, portable, roots = text[len(CASE):], True, _roots_for(CASE, case_path)
    elif text.startswith(DATA):
        relative, portable, roots = text[len(DATA):], True, (_data_root(),)
    else:
        candidate = Path(os.path.expandvars(text)).expanduser()
        if candidate.is_absolute():
            path = candidate.resolve()
            if not path.exists():
                raise AssetRefError(
                    text, kind, "absolute path does not exist on this machine",
                    searched=(path,),
                    hint="an absolute path is not portable: write 'lib:<name>' for a shipped asset "
                         "or a plain relative name for a file next to the case",
                )
            return ResolvedAsset(ref=text, kind=kind, path=path, root=path.parent, portable=False)
        relative, portable, roots = text, True, _roots_for(CASE, case_path)
    if not relative:
        raise AssetRefError(text, kind, "nothing after the prefix", searched=roots)

    for root in roots:
        path = (root / relative).resolve()
        # ``lib:../../elsewhere`` used to resolve happily: a prefixed reference is meant to
        # stay inside the root it names, so a resolved path outside it is an error rather
        # than a quiet escape.
        try:
            path.relative_to(Path(root).resolve())
        except ValueError:
            continue
        if path.is_file():
            return ResolvedAsset(ref=text, kind=kind, path=path, root=root, portable=portable)

    raise AssetRefError(
        text, kind, "not found under any known root", searched=roots,
        hint="relative names resolve against the case file's own folder; 'lib:' against the "
             "installed vehicle library (velch vehicle dir); 'data:' against the corpus root",
    )
