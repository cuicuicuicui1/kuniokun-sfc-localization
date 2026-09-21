"""Isolate code from text: take the shipped Chinese ROM but restore the four code
hook sites from the untouched original.  The translated bytes then get rendered by
the ORIGINAL drawer at the ORIGINAL cost (Japanese glyphs, garbage but harmless).

If the game runs smoothly here, my replacement code (cost/timing or logic) is the
cause of the freeze; if it still freezes, the cause is in the text encoding.
"""
import struct, zlib
BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
cn = bytearray(open(BASE + 'kuniokun_cn.smc', 'rb').read())
orig = open(BASE + 'work_kuniokun_2mb.smc', 'rb').read()

SITES = [
    (0x01FA30, 4, 'drawer hook -> JML $3E:8200'),
    (0x00FC79, 4, 'widget preload hook'),
    (0x00FC85, 2, 'widget nop'),
    (0x00FC92, 4, 'widget dispatch hook'),
]
for off, n, what in SITES:
    print('%06X %s' % (off, what))
    print('   cn : %s' % ' '.join('%02X' % b for b in cn[off:off + n]))
    print('   orig: %s' % ' '.join('%02X' % b for b in orig[off:off + n]))
    cn[off:off + n] = orig[off:off + n]

body = bytearray(cn)
body[0x7FC0:0x7FC4] = b'\x00\x00\x00\x00'
ck = (sum(body) + 0x1FE) & 0xFFFF
cn[0x7FDC:0x7FDE] = struct.pack('<H', ck ^ 0xFFFF)
cn[0x7FDE:0x7FE0] = struct.pack('<H', ck)
print('checksum=%04X' % ck)
open(BASE + 'kuniokun_nocn.smc', 'wb').write(bytes(cn))
open(BASE + 'dl/roms/knocn.smc', 'wb').write(bytes(cn))
print('written kuniokun_nocn.smc crc32=%08X' % (zlib.crc32(bytes(cn)) & 0xFFFFFFFF))