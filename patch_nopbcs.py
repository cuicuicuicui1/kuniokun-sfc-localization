"""Diagnostic: neutralise the six "a sub-step said stop" branches in the text
driver, to see whether the freeze lives in those sub-steps or elsewhere.

Driver (bank $03, ROM 0x01EE70):
    EE7A: jsr $ef2d / EE7D: bcs $eeb5      <- six of these pairs
    ...
    EE93: jsr $fa0b / EE96: bcs $eeb5
Each bcs is 2 bytes (B0 36).  Replacing it with EA EA makes the driver run the
draw loop unconditionally; if the Chinese text then starts appearing, the
blocker is one of the six sub-steps and I bisect from there.
"""
BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
import struct, zlib

src = bytearray(open(BASE + 'kuniokun_cn.smc', 'rb').read())

SITES = [0x01EE7D, 0x01EE82, 0x01EE87, 0x01EE8C, 0x01EE91, 0x01EE96]
for s in SITES:
    got = bytes(src[s:s + 2])
    print('%06X: %s' % (s, got.hex()), end='')
    assert got[0] == 0xB0, got
    src[s:s + 2] = bytes.fromhex('EAEA')
    print('  dist=%02X -> EA EA' % got[1])

# Also report the byte after each jsr site, for the record
for s in SITES:
    print('  around %06X: %s' % (s - 3, ' '.join('%02X' % b for b in src[s - 3:s + 3])))

body = bytearray(src)
body[0x7FC0:0x7FC4] = b'\x00\x00\x00\x00'
ck = (sum(body) + 0x1FE) & 0xFFFF
src[0x7FDC:0x7FDE] = struct.pack('<H', ck ^ 0xFFFF)
src[0x7FDE:0x7FE0] = struct.pack('<H', ck)
print('checksum=%04X' % ck)

open(BASE + 'kuniokun_nopbcs.smc', 'wb').write(bytes(src))
open(BASE + 'dl/roms/knopbcs.smc', 'wb').write(bytes(src))
print('written kuniokun_nopbcs.smc crc32=%08X' % (zlib.crc32(bytes(src)) & 0xFFFFFFFF))