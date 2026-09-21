"""Fix the box-wipe content check in verify16.py.

The row runs are 56 bytes each (4 byte header + 26 blank words), so the second
run starts at offset 56 -- the check read headers four bytes into the data.
The file has mixed line endings, so normalise to LF while patching.
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(BASE, 'verify16.py')
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')

old = """        for k in (0, 0x20):
            base = 4 + k * (4 + 52)
            lo, hi, vm, cnt = w[0x0B00 + base], w[0x0B00 + base + 1], \\
                w[0x0B00 + base + 2], w[0x0B00 + base + 3]
            want_addr = (0x7C03 + (cur & 0x0F) * 0x40 + k * 0x20) & 0xFFFF
"""
new = """        # two runs per row: 26 upper halves at $7C03+row*$40 and the 26 lower
        # halves $20 words further on; each run is a 4 byte header plus 52 bytes
        for k, delta in enumerate((0, 0x20)):
            base = k * (4 + 52)
            lo, hi, vm, cnt = w[0x0B00 + base], w[0x0B00 + base + 1], \\
                w[0x0B00 + base + 2], w[0x0B00 + base + 3]
            want_addr = (0x7C03 + (cur & 0x0F) * 0x40 + delta) & 0xFFFF
"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('E content check fixed (and verify16.py normalised to LF)')