"""Peek at the SDITT turnout profile library: mileage maps and .prr headers."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\WRProfile-07(009)-1_18")


def text_of(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def main() -> None:
    for name in ("07(009)-Mileage/07(009)-Mileage-qjbg.txt",
                 "07(009)-Mileage/07(009)-Mileage-cxg.txt"):
        path = ROOT / name
        lines = [line.rstrip() for line in text_of(path).splitlines() if line.strip()]
        print(f"=== {path.name}: {len(lines)} non-empty lines")
        for line in lines[:10]:
            print("   ", line)
        print("    ...")
        for line in lines[-3:]:
            print("   ", line)

    prr = ROOT / "07(009)-qjbg-20200418" / "07(009)-qjbg-20200418-10.prr"
    body = text_of(prr).splitlines()
    print(f"\n=== {prr.name}: {len(body)} lines")
    for line in body[:14]:
        print("   ", line)
    print("    ...")
    for line in body[-3:]:
        print("   ", line)


if __name__ == "__main__":
    main()
