"""Read the parts of a Simpack ``.spck`` ASCII model that we can verify, and nothing else.

A ``.spck`` is Simpack's ASCII model database (``!file.version=3.6`` in the first line). It is a
flat list of assignments::

    force.type (      $F_PS_Damp_FL   ) = 6            ! Type
    force.par  ( 3 ,  $F_PS_Damp_FL   ) = $G_PrimSusp.$_Prim_Damp_d ! 一系垂向减震器阻尼
    subvar.str (      $_Prim_Damp_d   ) = '10000'      ! $G_PrimSusp.$_Prim_Damp_d

Two properties matter for reading it honestly:

* values are often **symbols**, and symbols may be **expressions** (``{ $G_PrimSusp.$_Prim_Damp_c/2 }``),
  so a reader that stops at "the value is a string" reports nothing useful;
* the trailing comment is the only place that says *what the number means*, and it is GBK-encoded.

What this module does **not** do: it does not build a vehicle, does not interpret element type
numbers, and does not decide whether the model is right.  It reports what the file says, with the
units and comments the file itself carries, so a human can compare it against our own parameters.
"""
from __future__ import annotations

import collections
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "SpckModel",
    "SpckModelError",
    "decode",
    "read_model",
    "suspension_table",
]

SCHEMA_VERSION = "velch-spck-inventory-v1"

_LINE = re.compile(
    r"^(?P<key>[A-Za-z][\w.]*)\s*"
    r"(?:\(\s*(?P<args>[^)]*)\s*\))?\s*"
    r"=\s*(?P<value>.*)$"
)
_SYMBOL = re.compile(r"\$[A-Za-z_]\w*(?:\.\$[A-Za-z_]\w*)*")
_ARITHMETIC = re.compile(r"^[-+*/(). 0-9eE]+$")
_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "latin-1")


class SpckModelError(RuntimeError):
    """The file is not a ``.spck`` we can read."""


def decode(raw: bytes) -> str:
    """Decode with the encodings Simpack actually emits, utf-8 first then GBK.

    A 2021x file mixes ASCII keys with GBK comments; decoding as latin-1 never fails but turns every
    Chinese comment into mojibake, and mojibake is worse than useless in a table of physical values.
    """
    for encoding in _ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def _split_value(text: str) -> tuple[str, str]:
    if "!" in text:
        core, _, note = text.partition("!")
        return core.strip(), note.strip()
    return text.strip(), ""


def _unquote(text: str) -> str:
    return text.strip().strip("'").strip()


@dataclass(frozen=True)
class _Record:
    key: str
    numbers: tuple[int, ...]
    name: str
    value: str
    note: str


class SpckModel:
    """One ``.spck`` file: records, subvariables, and symbol resolution."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise SpckModelError(f"no such model file: {self.path}")
        self._records: list[_Record] = []
        try:
            text = decode(self.path.read_bytes())
        except OSError as error:
            raise SpckModelError(f"cannot read {self.path}: {error}") from error
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("!"):
                continue
            match = _LINE.match(stripped)
            if not match:
                continue
            args = (match.group("args") or "").strip()
            value, note = _split_value(match.group("value"))
            numbers: list[int] = []
            name = ""
            for part in args.split(",") if args else ():
                piece = part.strip()
                if piece.startswith("$"):
                    name = piece
                    continue
                try:
                    numbers.append(int(piece))
                except ValueError:
                    name = piece
            self._records.append(_Record(match.group("key"), tuple(numbers), name, value, note))
        if not any(record.key.startswith("subvar.") for record in self._records):
            raise SpckModelError(
                f"{self.path.name} carries no subvariables: this is not a .spck ASCII model"
            )
        self._values, self._comments = self._resolve()

    # -- raw access ---------------------------------------------------------------------------
    @property
    def version(self) -> str | None:
        for record in self._records:
            if record.key == "version.number":
                return record.value
        return None

    def value(self, key: str, *, name: str | None = None) -> str | None:
        for record in self._records:
            if record.key != key:
                continue
            if name is not None and record.name != name:
                continue
            return record.value
        return None

    def grouped(self, prefix: str) -> dict[str, dict[str, dict[tuple[int, ...], tuple[str, str]]]]:
        table: dict[str, dict[str, dict[tuple[int, ...], tuple[str, str]]]] = collections.defaultdict(
            lambda: collections.defaultdict(dict)
        )
        for record in self._records:
            if not record.key.startswith(prefix + "."):
                continue
            tail = record.key[len(prefix) + 1:]
            table[record.name][tail][record.numbers] = (record.value, record.note)
        return table

    def counts(self) -> dict[str, int]:
        return {
            "records": len(self._records),
            "subvariables": len(self._values),
            "bodies": len({record.name for record in self._records if record.key.startswith("body.")}),
            "markers": len({record.name for record in self._records if record.key.startswith("marker.")}),
            "joints": len({record.name for record in self._records if record.key.startswith("joint.")}),
            "forces": len({record.name for record in self._records if record.key.startswith("force.")}),
        }

    # -- subvariables -------------------------------------------------------------------------
    @property
    def subvariables(self) -> dict[str, float]:
        return dict(self._values)

    @property
    def comments(self) -> dict[str, str]:
        return dict(self._comments)

    def _resolve(self) -> tuple[dict[str, float], dict[str, str]]:
        raw: dict[str, str] = {}
        comments: dict[str, str] = {}
        for record in self._records:
            if record.key == "subvar.str" and record.name:
                raw[record.name] = record.value
            elif record.key == "subvar.txt" and record.name:
                comments[record.name] = _unquote(record.value)
        values: dict[str, float] = {}
        # A few passes: a subvariable may be written in terms of one that appears later.
        for _ in range(6):
            for name, expression in raw.items():
                if name in values:
                    continue
                resolved = self.number(expression, values)
                if resolved is not None:
                    values[name] = resolved
        return values, comments

    @staticmethod
    def _lookup(symbol: str, values: dict[str, float]) -> float | None:
        """Resolve ``$G_PrimSusp.$_Prim_Damp_d`` through its short name ``$_Prim_Damp_d``.

        Simpack stores each global once under its short name but references it qualified by the
        group it lives in, so without this fallback every force parameter in a real file would stay
        unresolved while the same number sits in the file under a shorter name.
        """
        if symbol in values:
            return values[symbol]
        short = "$" + symbol.split("$")[-1]
        return values.get(short)

    @classmethod
    def number(cls, expression: str, values: dict[str, float]) -> float | None:
        """Resolve one assignment value: a literal, a symbol, or a symbol arithmetic expression.

        Returns ``None`` — never a guess — when a symbol is unknown or the text is not arithmetic.
        """
        text = _unquote(expression).replace("{", " ").replace("}", " ")
        for _ in range(8):
            found = _SYMBOL.findall(text)
            if not found:
                break
            for symbol in set(found):
                resolved = cls._lookup(symbol, values)
                if resolved is None:
                    return None
                text = text.replace(symbol, repr(resolved))
        text = text.strip()
        if not text or not _ARITHMETIC.match(text):
            return None
        try:
            return float(eval(text, {"__builtins__": {}}, {}))  # noqa: S307 - guard is digits+operators
        except Exception:  # pragma: no cover - defensive
            return None


    def number_of(self, expression: str) -> float | None:
        return self.number(expression, self._values)

    def inventory(self) -> dict[str, Any]:
        """Everything this module can state about the file, in one JSON-serialisable dict."""
        forces = self.grouped("force")
        force_rows: list[dict[str, Any]] = []
        schema: dict[str, set[str]] = collections.defaultdict(set)
        for name in sorted(forces):
            block = forces[name]
            kind = block.get("type", {}).get((), ("", ""))[0]
            parameters: dict[str, Any] = {}
            for numbers, (value, note) in sorted(block.get("par", {}).items()):
                parameters[",".join(str(index) for index in numbers)] = {
                    "value": self.number_of(value),
                    "raw": value,
                    "comment": note,
                }
                schema[kind + "|" + str(block.get("type", {}).get((), ("", ""))[1])].add(
                    f"{numbers}:{note.split(']')[-1].strip() if ']' in note else note}"
                )
            force_rows.append({
                "name": name,
                "type": kind,
                "from": block.get("from", {}).get((), ("", ""))[0],
                "to": block.get("to", {}).get((), ("", ""))[0],
                "parameters": parameters,
            })
        return {
            "schema_version": SCHEMA_VERSION,
            "file": str(self.path),
            "version": self.version,
            "counts": self.counts(),
            "subvariables": {
                name: {"value": self._values[name], "comment": self._comments.get(name, "")}
                for name in sorted(self._values)
            },
            "unresolved": sorted(set(self._subvariable_names()) - set(self._values)),
            "force_types": {kind: sorted(entries) for kind, entries in sorted(schema.items())},
            "forces": force_rows,
        }

    def _subvariable_names(self) -> set[str]:
        return {record.name for record in self._records if record.key == "subvar.str" and record.name}

    def to_json(self, destination: Path | str) -> Path:
        target = Path(destination)
        target.write_text(
            json.dumps(self.inventory(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return target


def read_model(path: Path | str) -> SpckModel:
    return SpckModel(path)


def suspension_table(model: SpckModel) -> list[tuple[str, float | None, str]]:
    """Rows of ``(symbol, value, comment)`` for everything the file itself calls a suspension part."""
    words = ("spr", "damp", "susp", "bush", "joint", "rollbar", "traction", "bump", "gearbox")
    rows = []
    for name in sorted(model.subvariables, key=str.lower):
        lowered = name.lower()
        comment = model.comments.get(name, "")
        if not any(word in lowered or word in comment.lower() for word in words):
            continue
        rows.append((name, model.subvariables[name], comment))
    return rows


def _main(argv: Iterable[str] | None = None) -> int:  # pragma: no cover - CLI lives in velch.cli
    import sys

    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print("usage: python -m velch.simpack_model <file.spck> [--json OUT]")
        return 2
    model = read_model(arguments[0])
    for symbol, value, comment in suspension_table(model):
        shown = f"{value:.6g}" if value is not None else "?"
        print(f"{symbol:36s} {shown:>15s}   {comment}")
    if "--json" in arguments:
        target = arguments[arguments.index("--json") + 1]
        model.to_json(target)
        print(f"wrote {target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
