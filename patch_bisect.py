"""Bisect which of my patched code hooks freezes the dialogue.

Sites (all in kuniokun_cn.smc, restored to the untouched original bytes):
  D 0x01FA30 4B  drawer hook      JML $3E:8200  <- AD 6F 03 C9
  W 0x00FC79 4B  widget preload   JML $3E:8000  <- BF C3 DB 03
  N 0x00FC85 2B  widget nop       EA EA         <- A9 03
  P 0x00FC92 4B  widget dispatch  JML $3E:8080  <- B7 22 C9 F2

Usage: python patch_bisect.py A          -> restore D only  (keep widget hooks)
       python patch_bisect.py B          -> restore W,N,P    (keep drawer hook)
       python patch_bisect.py W          -> restore only the preload hook
       python patch_bisect.py NP         -> restore nop+dispatch reverted partially
"""
import struct, sys, zlib

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
SITES = {
    'D': (0x01FA30, 4, 'drawer hook'),
    'W': (0x00FC79, 4, 'widget preload'),
    'N': (0x00FC85, 2, 'widget nop'),
    'P': (0x00FC92, 4, 'widget dispatch'),
}

which = (sys.argv[1] if len(sys.argv) > 1 else 'A').upper()
cn = bytearray(open(BASE + 'kuniokun_cn.smc', 'rb').read())
orig = open(BASE + 'work_kuniokun_2mb.smc', 'rb').read()

for k, (off, n, what) in SITES.items():
    mark = 'RESTORE' if k in which else 'keep   '
    print('%s %06X %-16s cn=%s orig=%s' % (
        mark, off, what,
        ' '.join('%02X' % b for b in cn[off:off + n]),
        ' '.join('%02X' % b for b in orig[off:off + n])))
    if k in which:
        cn[off:off + n] = orig[off:off + n]

body = bytearray(cn)
body[0x7FC0:0x7FC4] = b'\x00\x00\x00\x00'
ck = (sum(body) + 0x1FE) & 0xFFFF
cn[0x7FDC:0x7FDE] = struct.pack('<H', ck ^ 0xFFFF)
cn[0x7FDE:0x7FE0] = struct.pack('<H', ck)

name = 'kuniokun_bis' + which.lower() + '.smc'
open(BASE + name, 'wb').write(bytes(cn))
open(BASE + 'dl/roms/kb' + which.lower() + '.smc', 'wb').write(bytes(cn))
print('-> %s  checksum=%04X crc32=%08X' % (name, ck, zlib.crc32(bytes(cn)) & 0xFFFFFFFF))