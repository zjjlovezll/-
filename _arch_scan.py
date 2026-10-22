import ast, pathlib
root = pathlib.Path("src/velch")
files = sorted(p for p in root.rglob("*.py"))
def modname(p):
    rel = p.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__": parts = parts[:-1]
    return ".".join(["velch"]+parts) if parts else "velch"
def package_of(m, is_pkg):
    parts = m.split(".")
    return ".".join(parts if is_pkg else parts[:-1])
mods = {}
for p in files:
    mods[modname(p)] = p
def resolve(m, node, is_pkg):
    if not node.level:
        return node.module or ""
    pkg = package_of(m, is_pkg).split(".")
    up = node.level - 1
    base = pkg[:len(pkg)-up] if up else pkg
    return ".".join(base + ([node.module] if node.module else []))
print("=== internal edges ===")
ext = {}
for m,p in sorted(mods.items()):
    tree = ast.parse(p.read_text(encoding="utf-8"))
    is_pkg = p.name == "__init__.py"
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            tgt = resolve(m, node, is_pkg)
            top = tgt.split(".")[0]
            if tgt in mods and tgt != m:
                print(f"{m:30s} -> {tgt:30s} :{node.lineno}")
            elif top not in ("velch","numpy","scipy","torch","math"):
                ext.setdefault(tgt,set()).add(m)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name in mods and a.name != m:
                    print(f"{m:30s} -> {a.name:30s} :{node.lineno}")
print()
print("=== subpackage external deps (non-stdlib) ===")
for k in sorted(ext):
    if k.startswith(("typing","dataclasses","pathlib","csv","json","math","hashlib","concurrent","collections","copy","tempfile","datetime","queue","os","sys","argparse","threading","time","traceback","itertools","re","abc","struct","textwrap","warnings","functools","subprocess","tkinter")):
        continue
    print(f"{k:24s} <- {sorted(ext[k])}")
