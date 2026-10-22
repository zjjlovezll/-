import pathlib

solver = pathlib.Path('src/velch/vehicle_solver.py')
text = solver.read_text(encoding='utf-8')
marker = '        self._active_body: dict[int, str] = {}'
assert text.count(marker) == 1, text.count(marker)
if 'self._support = case.support_compliance' not in text:
    text = text.replace(marker, marker + '\n        self._support = case.support_compliance', 1)
    solver.write_text(text, encoding='utf-8')
    print('solver: _support defined')
else:
    print('solver: _support already defined')

geo = pathlib.Path('src/velch/support_compliance.py')
text = geo.read_text(encoding='utf-8')
old = """    # Two full pitches with supports at 0, 1 and 2 pitch, plus a short overhang so
    # the loaded span never sees the free end.
    spans = 2"""
new = """    # Three pitches: the load sits in the middle one, whose two neighbouring
    # supports are interior, so the clamped ends are two pitches away.
    spans = 3"""
assert old in text
text = text.replace(old, new, 1)
geo.write_text(text, encoding='utf-8')
print('geometry: three pitches')
