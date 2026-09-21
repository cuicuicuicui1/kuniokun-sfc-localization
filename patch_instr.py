"""Instrument the *built* Chinese ROM in place (no rebuild) to find the freeze.

Two recorders, both in the bank $3E scratch area:

  driver entry  (ROM 0x01EE70)  ->  $3E:8400
      counts how often the per-frame text driver is entered, so we can tell
      "the engine stopped being called" from "the engine aborts every frame".

  drawer entry  (ROM 0x01FA30 JML target) -> $3E:8480
      records, per call: the caller's return address (which of the three
      JSR $FA30 sites), A at entry, and $12 at entry.

Record layout (WRAM $0C00+):
  $0C00/$0C01 driver entry count lo/hi
  $0C0D       drawer call count
  $0C0E/$0C0F drawer caller return address lo/hi
  $0C10       $12 at drawer entry
  $0C11       A at drawer entry
"""
import struct

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/'
SRC = BASE + 'kuniokun_cn.smc'
DST = BASE + 'kuniokun_instr.smc'
DST2 = BASE + 'dl/roms/kinstr.smc'

instr = bytearray(open(SRC, 'rb').read())
orig = open(BASE + 'work_kuniokun_2mb.smc', 'rb').read()
assert len(instr) == 2097152

def rom_to_snes(off):
    return off // 0x8000, 0x8000 + (off % 0x8000)

def snes_to_rom(bank, addr):
    return bank * 0x8000 + (addr - 0x8000)

def put(rom_off, data, expect=None, tag=''):
    if expect is not None:
        got = bytes(instr[rom_off:rom_off + len(expect)])
        assert got == expect, 'signature mismatch at %06X %s: %s != %s' % (
            rom_off, tag, got.hex(), expect.hex())
    instr[rom_off:rom_off + len(data)] = data

# ---------------------------------------------------------------- driver entry
# 0x01EE70: php phb sep #$30 phk plb  / 0x01EE76: lda $0373
DRV = 0x01EE70
put(DRV, bytes.fromhex('5C0084 3E'.replace(' ', '')),
    expect=bytes.fromhex('088BE2304BAB'), tag='driver entry')

rec = bytearray()
def emit(*bs):
    for b in bs:
        rec.append(b if isinstance(b, int) else b)

# counter, preserving A and the flags (the driver saves flags with php)
rec += bytes([0x08])                      # PHP
rec += bytes([0x48])                      # PHA
rec += bytes([0xEE, 0x00, 0x0C])          # INC $0C00
rec += bytes([0xD0, 0x03])                # BNE +3
rec += bytes([0xEE, 0x01, 0x0C])          # INC $0C01
rec += bytes([0x68])                      # PLA
rec += bytes([0x28])                      # PLP
# replay the original entry prologue
rec += bytes([0x08, 0x8B, 0xE2, 0x30, 0x4B, 0xAB])
# continue right after it: JML operand is bank:address, and the driver lives in
# bank $03 (ROM 0x01EE76 is bank $03 addr $EE76 for a LoROM image).
def jml(bank, addr):
    return bytes([0x5C, addr & 0xFF, (addr >> 8) & 0xFF, bank & 0xFF])

rec += jml(0x03, 0xEE76)
assert len(rec) <= 64, len(rec)
put(0x1F0400, bytes(rec), tag='driver recorder')
print('driver recorder %d bytes at 0x1F0400 -> JML $03:EE76' % len(rec))

# ---------------------------------------------------------------- drawer entry
# 0x01FA30 currently holds JML $3E:8200 (the patched drawer copy)
put(0x01FA30, bytes.fromhex('5C0084 3E'.replace(' ', '')),
    expect=bytes.fromhex('5C0082 3E'.replace(' ', '')), tag='drawer hook')

d = bytearray()
d += bytes([0x48])                        # PHA
d += bytes([0xBA])                        # TSX   (X = S)
d += bytes([0xBD, 0x01, 0x01])            # LDA $0101,X  -> return address low
d += bytes([0x8D, 0x0E, 0x0C])            # STA $0C0E
d += bytes([0xBD, 0x02, 0x01])            # LDA $0102,X  -> return address high
d += bytes([0x8D, 0x0F, 0x0C])            # STA $0C0F
d += bytes([0xA5, 0x12])                  # LDA $12
d += bytes([0x8D, 0x10, 0x0C])            # STA $0C10
d += bytes([0x68])                        # PLA  (restore A = code)
d += bytes([0x8D, 0x11, 0x0C])            # STA $0C11
d += bytes([0xEE, 0x0D, 0x0C])            # INC $0C0D (call count)
d += jml(0x3E, 0x8200)
assert len(d) <= 64, len(d)
put(0x1F0480, bytes(d), tag='drawer recorder')
print('drawer recorder %d bytes at 0x1F0480 -> JML $3E:8200' % len(d))

# ---------------------------------------------------------------- checksum
# This ROM stores $FFDC/$FFDD = complement, $FFDE/$FFDF = checksum.
hdr = 0x7FC0
assert bytes(instr[hdr:hdr + 4]) == b'\x00\x00\x00\x00' or True
body = bytearray(instr)
body[hdr:hdr + 4] = b'\x00\x00\x00\x00'
ck = (sum(body) + 0x1FE) & 0xFFFF
comp = ck ^ 0xFFFF
instr[0x7FDC:0x7FDE] = struct.pack('<H', comp)
instr[0x7FDE:0x7FE0] = struct.pack('<H', ck)
print('checksum=%04X complement=%04X (sum check %04X)' % (ck, comp, (ck + comp) & 0xFFFF))

open(DST, 'wb').write(bytes(instr))
open(DST2, 'wb').write(bytes(instr))
import zlib
print('written', DST, 'crc32=%08X' % (zlib.crc32(bytes(instr)) & 0xFFFFFFFF))