import pathlib

p = pathlib.Path('validation/crh380a_m/cmp_s1e_full.py')
s = p.read_text(encoding='utf-8')
old = '''for directory in ("out_Y_base", "out_Y_support", "out_Z_full_local_rail",
                       "out_Z_full_cz20", "out_Z_full_kz100"):'''
new = '''for directory in ("out_Y_base", "out_Y_support", "out_Z_full_local_rail",
                       "out_Z_full_cz20", "out_Z_full_kz100",
                       "out_W_full_series199"):'''
if old in s:
    p.write_text(s.replace(old, new), encoding='utf-8')
    print('patched')
else:
    print([line for line in s.splitlines() if 'out_Z_full_kz100' in line])
