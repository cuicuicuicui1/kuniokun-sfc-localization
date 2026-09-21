# -*- coding: utf-8 -*-
"""Teach the checkers about the one byte codes and the dropped sanitizer."""
import io

# ---------------------------------------------------------------- builder
P = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/cnbuild5.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
old = """               'no_translate': sorted(NO_TRANSLATE),"""
assert s.count(old) == 1
s = s.replace(old, """               'no_translate': sorted(NO_TRANSLATE),
               'fixed': {k: v for k, v in FIXED_CODES.items()},
               'fixed0': FIXED0,
               'fixed_n': FIXED_N,""")
io.open(P, 'w', encoding='utf-8', newline='\n').write(s)

# ---------------------------------------------------------------- check16
P = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/check16.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')
old = """counter = cb.HOOK_COPY1
for hook in (cb.HOOK_COPY1, cb.HOOK_COPY2):
    got = rom[hook:hook + 3]
    print('%-22s %s %s' % ('sanitize hook $%06X' % hook, got.hex(' '),
                           'OK' if got == bytes([0x20, sa & 0xFF, sa >> 8])
                           else 'MISMATCH'))"""
assert s.count(old) == 1
s = s.replace(old, """for hook in (cb.HOOK_COPY1, cb.HOOK_COPY2):
    got = rom[hook:hook + 3]
    print('%-22s %s %s' % ('sanitize call $%06X' % hook, got.hex(' '),
                           'OK (removed)' if got == bytes([0x9D, 0xEA, 0x03])
                           else 'MISMATCH'))""")

old = """left = rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + cb.SLOTS]
right = rom[cb.E3_SLOTPAIR + cb.SLOTS:cb.E3_SLOTPAIR + 2 * cb.SLOTS]
print('slot table %d slots: left %s right %s'
      % (cb.SLOTS, left[:8].hex(' '), right[:8].hex(' ')))"""
assert s.count(old) == 1
s = s.replace(old, """params = __import__('json').load(open('cn_build_params.json', encoding='utf-8'))
NSLOT = params['slots']
left = rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + NSLOT]
right = rom[cb.E3_SLOTPAIR + NSLOT:cb.E3_SLOTPAIR + 2 * NSLOT]
print('slot table %d slots: left %s right %s'
      % (NSLOT, left[:8].hex(' '), right[:8].hex(' ')))""")

old = """params = __import__('json').load(open('cn_build_params.json', encoding='utf-8'))
cell = __import__('json').load(open('cn_glyph_cell.json', encoding='utf-8'))"""
assert s.count(old) == 1
s = s.replace(old, """cell = __import__('json').load(open('cn_glyph_cell.json', encoding='utf-8'))""")

old = """for name, start, length in (('drawer', cb.E3_DRAWER, 747),
                            ('wipe', cb.E3_WIPE, 416),
                            ('arm', cb.E3_ARM, 40),
                            ('sanitize', cb.B3_SANITIZE, 14)):"""
assert s.count(old) == 1
s = s.replace(old, """for name, start, length in (('drawer', cb.E3_DRAWER, 817),
                            ('wipe', cb.E3_WIPE, 429),
                            ('arm', cb.E3_ARM, 47)):""")

old = """print('glyph cell map entries: %d' % len(cell))"""
assert s.count(old) == 1
s = s.replace(old, """print('glyph cell map entries: %d ; one byte codes %s'
      % (len(cell), ' '.join('%s=%02X' % (k, v)
                             for k, v in sorted(params['fixed'].items(),
                                                key=lambda kv: kv[1]))))""")
io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('check16 patched')