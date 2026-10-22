import ast, pathlib
root = pathlib.Path("src/velch")
for p in sorted(root.rglob("*.py")):
    if "__pycache__" in str(p): continue
    src = p.read_text(encoding="utf-8")
    tree = ast.parse(src)
    rel = p.relative_to(root).as_posix()
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            kind = "class" if isinstance(node,ast.ClassDef) else "def"
            print(f"src/velch/{rel}:{node.lineno}: {kind} {node.name}")
            if isinstance(node,ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub,(ast.FunctionDef,)):
                        print(f"src/velch/{rel}:{sub.lineno}:     .{sub.name}")
