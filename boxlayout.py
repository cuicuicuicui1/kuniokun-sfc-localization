"""Measure the box layout constraints of the real dialogue pipeline.

The dialogue drawer (ROM 0x01FA30) stages tilemap entries for a 16-row x 26-col
box at VRAM $7C00 with a 0x40-word row step.  Its column guard is `CMP #$1A`
(cols 0..25; anything past that is silently skipped).  Slot planning needs:
  * max cells per rendered line
  * max lines per page (a page ends at {F2F4})
  * total cells per page
"""
import json
import re
from collections import Counter

TR = json.load(open('cn_translation.json', encoding='utf-8'))
TOKEN = re.compile(r'(\{[0-9A-Fa-f]{2,4}\})')


def cells(text):
    """Rendered cell count of one line (Chinese = 1 cell, token bytes = 1 each)."""
    n = 0
    for part in TOKEN.split(text):
        if not part:
            continue
        if TOKEN.fullmatch(part):
            h = part[1:-1]
            if len(h) & 1:
                h = '0' + h
            b = bytes.fromhex(h)
            if len(b) == 2 and b[0] == 0xF2:
                continue
            n += len(b)
        else:
            n += len(part)
    return n


pages_over_4 = []
lines_over_24 = []
line_hist = Counter()
page_hist = Counter()
for k, v in TR.items():
    for page in v.split('{F2F4}'):
        lines = [l for l in page.split('{F2F6}')]
        # drop a trailing empty segment (page ends right at the break)
        if lines and lines[-1].strip() == '':
            lines = lines[:-1]
        real = [l for l in lines if l.strip() not in ('', '{F0}')]
        page_hist[len(real)] += 1
        if len(real) > 4:
            pages_over_4.append((k, len(real), sum(cells(l) for l in real)))
        for l in lines:
            w = cells(l)
            line_hist[w] += 1
            if w > 24:
                lines_over_24.append((k, w, l[:40]))

print('line width histogram (cells):', dict(sorted(line_hist.items())))
print('lines per page histogram    :', dict(sorted(page_hist.items())))
print()
print('lines wider than 24 cells:', len(lines_over_24))
for k, w, s in lines_over_24[:20]:
    print('   %s  %2d cells  %r' % (k, w, s))
print()
print('pages with more than 4 lines:', len(pages_over_4))
for k, n, tot in pages_over_4[:20]:
    print('   %s  %d lines, %d cells total' % (k, n, tot))