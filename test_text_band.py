"""PPU V-scroll mapping contract: no next-row pixel leakage at scanline215.

Static geometry plus original-template protection, not a full PPU model.
Headless screenshot/VRAM matching independently verified the +1 convention.
"""
from pathlib import Path
rom=Path('kuniokun_cn.smc').read_bytes()
original=Path('dl/roms/kuniokun__SF8127.smc').read_bytes()
assert rom[0x1EACA:0x1EACC]==original[0x1EACA:0x1EACC]==bytes.fromhex('AA 03')
a=bytearray(original[0x1EACC:0x1EAEB]);a[23]=0x47
assert rom[0x1EACC:0x1EAEB]==a, 'other HDMA fields/records were altered'
for row in range(16):
 old=original[0x1EAF7+row];new=rom[0x1EAF7+row]
 assert new==(old-1)&255
 top=(184+new+1)&255;last=(215+new+1)&255
 assert top==row*16 and last==(row*16+31)&255, (row,top,last)
 assert (215+old+1)&255==(row*16+32)&255, 'negative geometry no longer leaks'
# Horizontal-scroll bytes for the lower border and all original native
# stores/increments remain untouched. Pace counter has independent ownership.
assert rom[0x1F082:0x1F085]==original[0x1F082:0x1F085]==bytes.fromhex('8D C1 03')
assert rom[0x1F56A:0x1F56D]==original[0x1F56A:0x1F56D]
assert rom[0x1EF34:0x1EF3A]==original[0x1EF34:0x1EF3A]
print('PASS two complete text rows; next-row leakage negative for all16 circular positions; native scroll and border records unchanged')
