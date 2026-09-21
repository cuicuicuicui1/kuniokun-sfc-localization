# -*- coding: utf-8 -*-
"""Build one-key test ROMs to answer a single question:

    which ROM block (if any) is Hero Senki's character font?

Method: overwrite a candidate block with a distinctive geometric pattern and
look at the on-screen text.  If text turns into that pattern, the block is the
font.  Each candidate gets its own pattern so a combo ROM is also readable.

Output: tests\hs_test_<letter>.sfc   (one candidate per file, plus a combo)
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROM = r"F:\BaiduNetdiskDownload\SFC\Hero Senki - Project Olympus (Japan) 优先级高\Hero Senki - Project Olympus (Japan).sfc"
OUT = os.path.join(HERE, 'tests')

# candidate blocks: (letter, start, end, human label)  -- tile-aligned 16 B units
CANDS = [
    ('A', 0x01C990, 0x01D7A0, '0x01C990  225 tiles  31x enrichment  <-- strongest candidate'),
    ('B', 0x00DE00, 0x00E760, '0x00DE00  150 tiles  28x enrichment'),
    ('C', 0x0757A0, 0x076390, '0x0757A0  191 tiles  21x enrichment'),
    ('D', 0x07D540, 0x07DA20, '0x07D540   78 tiles  20x enrichment'),
    ('E', 0x15BD60, 0x15C330, '0x15BD60   93 tiles  19x enrichment'),
    ('F', 0x1209A0, 0x1212E0, '0x1209A0  148 tiles  15x enrichment'),
]


def tile(rows):
    """8 strings of 8 chars ('#'/'.') -> 16 B SNES 2bpp planar, ink = value 3."""
    b = bytearray()
    for r in rows:
        v = 0
        for x in range(8):
            if r[x] == '#':
                v |= 0x80 >> x
        b.append(v)
        b.append(v)
    return bytes(b)


def grid(fn):
    return [''.join('#' if fn(x, y) else '.' for x in range(8)) for y in range(8)]


PATTERNS = {
    'A': ('ring  O',    grid(lambda x, y: 6 <= (x - 3.5) ** 2 + (y - 3.5) ** 2 <= 13)),
    'B': ('X',          grid(lambda x, y: x == y or x == 7 - y)),
    'C': ('checker',    grid(lambda x, y: ((x // 2) + (y // 2)) % 2 == 0)),
    'D': ('h-stripes',  grid(lambda x, y: (y // 2) % 2 == 0)),
    'E': ('v-stripes',  grid(lambda x, y: (x // 2) % 2 == 0)),
    'F': ('solid',      grid(lambda x, y: True)),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    rom = open(ROM, 'rb').read()
    assert len(rom) == 0x180000, len(rom)
    print('source ROM: %d bytes' % len(rom))

    for letter, name, rows in [(l, n, r) for l, (n, r) in PATTERNS.items()]:
        print('--- pattern %s (%s) ---' % (letter, name))
        for r in rows:
            print('   ', r)

    def build(selected, suffix):
        data = bytearray(rom)
        for letter, lo, hi, _ in CANDS:
            if letter not in selected:
                continue
            t = tile(PATTERNS[letter][1])
            n = (hi - lo) // 16
            data[lo:lo + n * 16] = t * n
        path = os.path.join(OUT, 'hs_test_%s.sfc' % suffix)
        open(path, 'wb').write(bytes(data))
        return path

    made = []
    for letter, lo, hi, label in CANDS:
        p = build([letter], letter)
        made.append((p, '%s  %s' % (letter, label)))
    made.append((build(['A', 'B', 'C'], 'COMBO_ABC'), 'COMBO  A+B+C patched in one ROM (fast path)'))

    print('\nwritten:')
    for p, label in made:
        print('  %-52s  %s' % (os.path.basename(p), label))
        print('      %s' % p)


if __name__ == '__main__':
    main()