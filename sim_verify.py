"""Deterministic verification of the patched renderer.

usage: python -u sim_verify.py <text_rom_off_hex> [max_cells]

Runs the translated string through the patched dispatcher in the 65816 sim and
checks, for every cell the string draws:
  * tilemap entry at $7800+cell == slottab[($7800+cell) & 0x7F] | $2400
  * VRAM tiles (base, base+1)   == the two halves of the expected glyph
  * the reserved tiles (0/1, $20/$21) were never written by the glyph DMA

Expected cells come from the translation text plus the BUILD-ORDER glyph map
(the same first-occurrence numbering cnbuild uses), not from re-encoding the
string in isolation.
"""
import json
import re
import sys

sys.path.insert(0, 'C:/Users/<user>/.zcode/workspace/default/sfc-recon')
import cnbuild
from cnbuild import Encoder, TOKEN, glyph32, build_slottab
from sim65816 import CPU
import kuniokun_map as _km

FA, FB = _km.FA, _km.FB
RESERVED = set([0x00]) | set(cnbuild.DECOR_TILES)
for _c in cnbuild.KEEP1.values():
    RESERVED.add(FA[_c]); RESERVED.add(FB[_c])

ROM = cnbuild.OUT_ROM
DISPATCH = 0x1F0080
CURSOR = 0x7800
TAB, NPAIRS = build_slottab()


def snes_of_rom(off):
    return (off // 0x8000, 0x8000 + (off % 0x8000))


def build_order():
    """char -> glyph number, exactly as cnbuild assigns them."""
    tr = json.load(open(cnbuild.BASE + '/cn_translation.json', encoding='utf-8'))
    recs = json.load(open(cnbuild.BASE + '/kuniokun_text.json', encoding='utf-8'))
    enc = Encoder()
    for table_off, count in cnbuild.TABLES:
        for r in sorted([r for r in recs if r['table_rom_off'] == table_off],
                        key=lambda r: r['index']):
            enc.encode(tr['%06X' % r['text_rom_off']])
    return enc, tr


def expected_cells(text, glyphs, limit=200):
    """[(kind, value)] in draw order; stops at the first 0xF2 control.

    kind 'cn'   -> value is the glyph number (2-byte Chinese code)
    kind 'orig' -> value is the original single-byte code (space, KEEP1
                   punctuation or a structural token), which goes through the
                   untouched original renderer path.
    """
    cells = []
    for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', text):
        if not part:
            continue
        m = TOKEN.fullmatch(part)
        if m:
            h = m.group(1)
            if len(h) & 1:
                h = '0' + h
            bs = bytes.fromhex(h)
            if bs[0] == 0xF2:
                cells.append(('ctrl', bs[0]))
                return cells[:limit]
            for byte in bs:
                cells.append(('orig', byte))
            continue
        for ch in part:
            if ch == ' ':
                cells.append(('orig', 0x00))
            elif ch in cnbuild.KEEP1:
                cells.append(('orig', cnbuild.KEEP1[ch]))
            else:
                cells.append(('cn', glyphs[ch]))
    return cells[:limit]


def run(rom, off, max_cells):
    # max_cells now means: stop as soon as the cursor has advanced this many cells
    cpu = CPU(rom)
    bank, addr = snes_of_rom(off)
    cpu.pbr = 0x3E
    cpu.pc = 0x8000 + (DISPATCH % 0x8000)
    cpu.m8 = True
    cpu.x8 = True
    cpu.y = 0
    cpu.bus.wr(0, 0x22, addr & 0xFF)
    cpu.bus.wr(0, 0x23, addr >> 8)
    cpu.bus.wr(0, 0x24, bank)
    cpu.bus.wr(0, 0x20, CURSOR & 0xFF)
    cpu.bus.wr(0, 0x21, CURSOR >> 8)
    cpu.vmain = 0x81  # set by the preload's JSR $F969 in the real flow
    cpu.s = 0x01FF
    cpu.push8(0x00)
    cpu.push8(0x00)
    for _ in range(400000):
        cpu.step()
        cur = (cpu.bus.rd(0, 0x21) << 8) | cpu.bus.rd(0, 0x20)
        if cur - CURSOR >= max_cells:
            break
    return cpu


def vram_tile(cpu, tile):
    out = bytearray()
    for y in range(8):
        w = cpu.vram[(0x6000 + tile * 8 + y) & 0x7FFF]
        out += bytes([w & 0xFF, w >> 8])
    return bytes(out)


def check(off, max_cells=110, quiet=False):
    key = '%06X' % off
    enc, tr = build_order()
    if key not in tr:
        return 'no translation for %s' % key
    text = tr[key]
    rev = {g: c for c, g in enc.glyphs.items()}
    amap = json.load(open(cnbuild.BASE + '/cn_addr_map.json'))
    cells = expected_cells(text, enc.glyphs)
    drawn = [c for c in cells if c[0] != 'ctrl']
    rom = open(ROM, 'rb').read()
    cpu = run(rom, amap[key], max(1, min(len(drawn), max_cells)))
    problems = []
    ncn = 0
    for c, (kind, g) in enumerate(cells):
        if c >= max_cells or kind == 'ctrl':
            break
        if kind == 'orig':
            want_top = FB[g] | 0x2400
            want_bot = FA[g] | 0x2400
            got = cpu.vram[(CURSOR + c) & 0x7FFF]
            if got != want_top:
                problems.append('cell %d orig code %02X entry %04X want %04X'
                                % (c, g, got, want_top))
            bot = cpu.vram[(CURSOR + c + 32) & 0x7FFF]
            if bot != want_bot:
                problems.append('cell %d orig code %02X bottom %04X want %04X'
                                % (c, g, bot, want_bot))
            continue
        ncn += 1
        ch = rev[g]
        slot = (CURSOR + c) & 0x7F
        base = TAB[slot]
        ent = cpu.vram[(CURSOR + c) & 0x7FFF]
        if ent != (base | 0x2400):
            problems.append('cell %d %r entry %04X want %04X'
                            % (c, ch, ent, base | 0x2400))
            continue
        if vram_tile(cpu, base) + vram_tile(cpu, base + 1) != glyph32(ch):
            problems.append('cell %d %r glyph bytes differ' % (c, ch))
    for tile in sorted(RESERVED):
        if any(vram_tile(cpu, tile)):
            problems.append('reserved tile %02X was written' % tile)
    if not quiet:
        print('0x%s %r' % (key, text[:70]))
        print('  cells=%d chinese=%d  ->  %d problems'
              % (min(len(cells), max_cells), ncn, len(problems)))
        for p in problems[:8]:
            print('    ' + p)
    return '%06X: %d problems' % (off, len(problems))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        check(int(sys.argv[1], 16),
              int(sys.argv[2]) if len(sys.argv) > 2 else 110)
    else:
        enc, tr = build_order()
        keys = sorted(tr, key=lambda s: int(s, 16))
        total = bad = 0
        for k in keys:
            r = check(int(k, 16), quiet=True)
            total += 1
            if not r.endswith('0 problems'):
                bad += 1
                print(r)
        print('%d/%d strings verified clean' % (total - bad, total))