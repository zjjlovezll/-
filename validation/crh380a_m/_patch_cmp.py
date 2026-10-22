import pathlib

p = pathlib.Path('validation/crh380a_m/cmp_support_ab.py')
s = p.read_text(encoding='utf-8')
old = '("out_X_base", "out_X_support")'
new = '("out_X_base", "out_X_support", "out_Z_local_rail")'
if old in s:
    p.write_text(s.replace(old, new), encoding='utf-8')
    print('patched targets')
else:
    print([line for line in s.splitlines() if 'for name in' in line])
