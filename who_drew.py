"""who_drew.py -- Decide whether the patched drawer's Chinese branch actually ran.

The message buffer at frame 1383 is
    47 26 00 00 09 | CB 3F | CD 49 | C6 01 | C5 15 | C5 29 | 01 | F2
i.e. speaker name (5 bytes, macro generated) + five Chinese characters encoded as
[0xC5+page][slot] + '!' + end-of-message.

Two hypotheses produce a tile pair per message cell:

  A) my drawer copy ran  -> cell = (SLOTPAIR[slot], SLOTPAIR[slot]+1)   [5 cells]
  B) the stock drawer ran -> cell = (FB[byte], FA[byte])                [10 cells]

The measured tiles of message columns 0..4 are
    (09C,09D) (0E6,0E7) (004,005) (03E,03F) (068,069)
so we compare those against both hypotheses, reading the ROM's own tables.
"""
import struct

ROM = r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"
FA = 0x01FA9E          # base-glyph table (256 bytes), used as the lower tile
FB = 0x01FB9E          # overlay table (dakuten dots), used as the upper tile
SLOTPAIR = 0x01E900    # one byte per slot: the even tile of the pair

rom = open(ROM, "rb").read()
fa = rom[FA:FA + 256]
fb = rom[FB:FB + 256]

slots = []
for i in range(0, 200):
    b = rom[SLOTPAIR + i]
    if b == 0:
        break
    slots.append(b)

msg = bytes([0xCB, 0x3F, 0xCD, 0x49, 0xC6, 0x01, 0xC5, 0x15, 0xC5, 0x29])
measured = [(0x09C, 0x09D), (0x0E6, 0x0E7), (0x004, 0x005), (0x03E, 0x03F), (0x068, 0x069)]

print("slot table: %d entries" % len(slots))
print("  head:", " ".join("%02X" % b for b in slots[:12]))
print("  SLOTPAIR[0x3F]=%02X [0x49]=%02X [0x01]=%02X [0x15]=%02X [0x29]=%02X"
      % tuple(slots[i] for i in (0x3F, 0x49, 0x01, 0x15, 0x29)))

print("\nhypothesis A: my drawer ran -- cell = (SLOTPAIR[slot], SLOTPAIR[slot]+1)")
hypA = []
i = 0
while i < len(msg) - 1:
    b = msg[i]
    if 0xC5 <= b <= 0xD0:
        s = msg[i + 1]
        t = slots[s] if s < len(slots) else None
        hypA.append((t, t + 1 if t is not None else None))
        i += 2
    else:
        hypA.append((fb[b], fa[b]))
        i += 1
for k, cell in enumerate(hypA):
    print("  cell %d: %s" % (k, cell))

print("\nhypothesis B: stock drawer ran -- cell = (FB[byte], FA[byte]) per byte")
hypB = [(fb[b], fa[b]) for b in msg]
for k, cell in enumerate(hypB):
    print("  cell %d: %s" % (k, cell))

print("\nmeasured tiles of message columns 0..4")
for k, cell in enumerate(measured):
    print("  col %d: (%03X,%03X)" % (k, cell[0], cell[1]))

print("\nverdict")
a_ok = [c for c in hypA[:5]] == measured
b_ok = [c for c in hypB[:5]] == measured
print("  columns 0..4 match hypothesis A (my branch): %s" % a_ok)
print("  columns 0..4 match hypothesis B (stock path): %s" % b_ok)
for k in range(5):
    print("   col %d: A=%s B=%s measured=%s"
          % (k, hypA[k] if k < len(hypA) else "-",
             hypB[k] if k < len(hypB) else "-", measured[k]))
print("\nconsecutive-pair check on measured tiles:",
      all(hi + 1 == lo for hi, lo in measured))
print("FA[0xC5..0xD1]: " + " ".join("%02X" % fa[b] for b in range(0xC5, 0xD2)))
print("FB[0xC5..0xD1]: " + " ".join("%02X" % fb[b] for b in range(0xC5, 0xD2)))