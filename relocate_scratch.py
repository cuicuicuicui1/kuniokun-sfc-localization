import re
p = 'cnbuild5.py'
s = open(p, encoding='utf-8').read()

# --- 1. relocate the scratch block -------------------------------------------------
# old base $0D40 (which the game itself writes: store sites at $0D40-$0D5F in banks $00/$01/$02/$05/$09/$0C)
# new base $1701 (no store site anywhere in the ROM; byte-identical over a 3000 frame probe)
NEW = {
    0x0D40: 0x1701,   # WIPE_TOP
    0x0D41: 0x1702,   # WIPE_BOT
    0x0D42: 0x1703,   # WIPE_CUR
    0x0D43: 0x1704,   # WIPE_PEND
    0x0D44: 0x1705,   # DRW_PA
    0x0D46: 0x1707,   # DRW_PB
    0x0D48: 0x1709,   # DRW_MODE
    0x0D4A: 0x170B,   # DRW_VMADD
    0x0D4C: 0x170D,   # DRW_ADDR2
    0x0D4E: 0x170F,   # DRW_ID
    0x0D50: 0x1711,   # DRW_T1
    0x0D51: 0x1712,   # DRW_T2
    0x0D52: 0x1713,   # DRW_T3
    0x0D53: 0x1714,   # DRW_T4
    0x0D54: 0x1715,   # WIPE_ADDR
    0x0D58: 0x1719,   # WIPE_LO
}
names = {
    'WIPE_TOP': 0x0D40, 'WIPE_BOT': 0x0D41, 'WIPE_CUR': 0x0D42, 'WIPE_PEND': 0x0D43,
    'DRW_PA': 0x0D44, 'DRW_PB': 0x0D46, 'DRW_MODE': 0x0D48, 'DRW_VMADD': 0x0D4A,
    'DRW_ADDR2': 0x0D4C, 'DRW_ID': 0x0D4E, 'DRW_T1': 0x0D50, 'DRW_T2': 0x0D51,
    'DRW_T3': 0x0D52, 'DRW_T4': 0x0D53, 'WIPE_ADDR': 0x0D54, 'WIPE_LO': 0x0D58,
}
n = 0
for name, old in names.items():
    new = NEW[old]
    pat = re.compile(r'^(%s\s*=\s*)0x%04X(\s*(?:#.*)?)$' % (name, old), re.M)
    s, k = pat.subn(lambda m: '%s0x%04X%s' % (m.group(1), new, m.group(2)), s)
    assert k == 1, (name, k)
    n += k
print('relocated %d constants' % n)

# --- 2. every emitted instruction must use the new page byte ----------------------
before = s.count('%02X 0D')
s = re.sub(r'%02X 0D\b', '%02X 17', s)
print('page byte rewritten at %d emit sites' % before)
assert '%02X %02X' not in s, 'a real two-placeholder format string got touched'

leftover = re.findall(r"'[0-9A-F ]*0D[0-9A-F ]*'", s)
print('leftover literal strings still containing 0D: %r' % (leftover[:8],))

open(p, 'w', encoding='utf-8', newline='\n').write(s)

# --- 3. report the new addresses --------------------------------------------------
import importlib.util
spec = importlib.util.spec_from_file_location('cb', p)
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)
print('new layout:')
for name in names:
    print('   %-10s = $%04X' % (name, getattr(cb, name)))