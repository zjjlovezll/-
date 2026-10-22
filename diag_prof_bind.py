import re
p=r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\mbs_db_substructure\CRH380A_M_Wheelset.spck"
raw=open(p,'rb').read().decode('gbk',errors='replace')
lines=raw.splitlines()
pat=re.compile(r'(prof|lat\.dist|gauge|RWR_Rail|rwp)',re.I)
hits=[(i+1,l.strip()) for i,l in enumerate(lines) if pat.search(l) and not l.strip().startswith('!')]
print('总行 %d, 命中 %d' % (len(lines),len(hits)))
for i,l in hits[:60]: print('%5d %s' % (i,l[:150]))
print('...')
for i,l in hits[-25:]: print('%5d %s' % (i,l[:150]))
