# -*- coding: utf-8 -*-
"""verify16: the slot table holds pair BASE TILES t (tiles t,t+1 free).  The drawer
computes VMADD = $6000 + t*8 words (cnbuild5.py:904-906) and puts tiles t,t+1 in the
cell entries (cnbuild5.py:897).  Hardware check: slot 42 -> tiles $D4/$D5/$D6/$D7."""
import io
P = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/verify16.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')

reps = [
    ('vm_a, vm_b = 0x6000 + pa * 16, 0x6000 + pb * 16',
     'vm_a, vm_b = 0x6000 + pa * 8, 0x6000 + pb * 8'),
    ('tiles = ((pa * 2, pa * 2 + 1), (pb * 2, pb * 2 + 1))',
     'tiles = ((pa, pa + 1), (pb, pb + 1))'),
]
for old, new in reps:
    assert s.count(old) == 1, old
    s = s.replace(old, new)

# drop the stale debug guard + flattened DEBUG print (3 lines, no body left behind)
lines = s.split('\n')
keep, dropped = [], []
for ln in lines:
    if 'if any(not (0 <= x < 256) for _t in tiles for x in _t)' in ln:
        dropped.append('guard')
        continue
    if "print('DEBUG key %s i %d code $%02X" in ln:
        dropped.append('print')
        continue
    if dropped == ['guard', 'print'] and ln.strip().startswith("'tiles %s' % (key"):
        dropped.append('print2')
        continue
    keep.append(ln)
assert dropped == ['guard', 'print', 'print2'], dropped
s = '\n'.join(keep)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('verify16 tile convention fixed')