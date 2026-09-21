# -*- coding: utf-8 -*-
"""Parse the static drawing script at $00:F9DB (status/parameter screen labels).

Format (interpreter at $00:F971):
  [addr_lo][addr_hi][count] then count cells; cell = (upper word, lower word)
  count < 0x80  -> literal tile numbers : upper = $2400 (blank), lower = byte|$2400
  count >= 0x80 -> font codes           : upper = FB[code], lower = FA[code]
Blocks end at the $FF sentinel.
"""
import kuniokun_map as km
C, FA, FB = km.CODE, km.FA, km.FB
orig = open('dl/roms/kuniokun__SF8127.smc','rb').read()
data = orig[0x00F9DB:0x00FB00]
y = 0
blocks = []
while y < len(data):
    hi = data[y]
    if hi == 0xFF:
        break
    lo = data[y]
    ahi = data[y+1]
    y += 2
    count = data[y]; y += 1
    vmadd = (ahi << 8) | lo
    if count == 0:
        blocks.append((vmadd, 0, 'empty', []))
        continue
    n = count & 0x7F
    if count & 0x80:
        codes = list(data[y:y+n]); y += n
        blocks.append((vmadd, n, 'text', codes))
    else:
        tiles = list(data[y:y+n]); y += n
        blocks.append((vmadd, n, 'tiles', tiles))
print('parsed %d blocks, stopped at y=$%02X (sentinel $%s)'
      % (len(blocks), y, data[y] if y < len(data) else 'EOF'))
lit, codes = set(), set()
for vmadd, n, kind, vals in blocks:
    label = ''.join(C.get(c, '{%02X}' % c) for c in vals) if kind == 'text' else ' '.join('%02X' % t for t in vals)
    print('  $%04X n=%2d %-5s  %s' % (vmadd, n, kind, label))
    if kind == 'tiles':
        lit.update(vals)
    else:
        codes.update(vals)
print('\nliteral tiles used: %s' % ' '.join('%02X' % t for t in sorted(lit)))
print('codes used: %d -> chars %s' % (len(codes), ''.join(C.get(c,'?') for c in sorted(codes))))
