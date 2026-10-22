import json, pathlib
base = pathlib.Path('validation/crh380a_m')
raw = json.loads((base/'case_S_hc_e0.5_v0.1.json').read_text(encoding='utf-8'))
raw['case_id'] = 'crh380a_m_z_full_local_rail'
raw['run']['duration_s'] = 1.2
raw['run']['x_start_m'] = 13.5
raw['track_dynamics'] = {'kind': 'local_compliant'}
raw.pop('support_compliance', None)
n = 35 + 2*len(raw['rail_templates'])*4
for t in raw['rail_templates']:
    t['mass_y_kg'] = 120.0
    t['mass_z_kg'] = 120.0
    t['support'] = {'k_y_n_m': 30e6, 'c_y_n_s_m': 20e3, 'k_z_n_m': 50e6, 'c_z_n_s_m': 40e3}
st = raw.get('initial_state', {})
q = list(st.get('q', [])) or [0.0]*35
v = list(st.get('v', [])) or [0.0]*35
raw['initial_state'] = {'q': (q + [0.0]*n)[:n], 'v': (v + [0.0]*n)[:n]}
(base/'case_Z_full_local_rail.json').write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding='utf-8')
print('wrote case_Z_full_local_rail.json, dof', n)
