#!/usr/bin/env python3
"""Locate text fonts via palette-usage signature: a 2-colour glyph font uses only
palette entries 0 and (2^bpp - 1). Scan windows and score by 'pure two-tone' tiles."""
import os, sys, zlib
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon2 import decode_tile2bpp, decode_tile4bpp, render_tiles

def palette_signature(body, start, ntiles, bpt, dec):
    hist = Counter()
    nonblank = 0; row0blank = 0; row7blank = 0
    for t in range(ntiles):
        o = start + t * bpt
        if o + bpt > len(body): return None
        g = dec(body, o)
        flat = [v for row in g for v in row]
        hist.update(flat)
        ink = sum(1 for v in flat if v)
        if ink: nonblank += 1
        if all(v == 0 for v in g[0]): row0blank += 1
        if all(v == 0 for v in g[7]): row7blank += 1
    tot = sum(hist.values())
    mx = (2 ** (bpt // 8)) - 1  # 3 for 2bpp, 15 for 4bpp
    # ink colours actually used = everything except 0
    inked = {k: v for k, v in hist.items() if k}
    pure = hist.get(mx, 0) / max(sum(inked.values()), 1)  # share of inked px that are the max colour
    return {'nonblank': nonblank / ntiles, 'row0blank': row0blank / ntiles,
            'row7blank': row7blank / ntiles, 'ink_ratio': sum(inked.values()) / tot,
            'pure': pure, 'ncolors': len(inked), 'hist': dict(sorted(hist.items()))}

def scan(path, tags):
    raw = open(path, 'rb').read()
    ch = 512 if len(raw) % 32768 == 512 else 0
    body = raw[ch:]
    print('# %s size=%d' % (os.path.basename(path), len(body)))
    out = []
    for bpt, dec, name in ((16, decode_tile2bpp, '2bpp'), (32, decode_tile4bpp, '4bpp')):
        ntiles = 128
        size = ntiles * bpt
        s = 0
        while s + size <= len(body):
            win = body[s:s + size]
            z = win.count(0); f = win.count(0xFF)
            if z + f > size * 0.6:
                s += 0x200; continue
            sg = palette_signature(body, s, ntiles, bpt, dec)
            if sg and sg['nonblank'] >= 0.90 and sg['row0blank'] >= 0.55 \
               and sg['row7blank'] >= 0.35 and 0.05 <= sg['ink_ratio'] <= 0.45 \
               and sg['pure'] >= 0.95 and sg['ncolors'] <= 3:
                out.append((bpt, name, s, sg))
            s += 0x200
    # dedupe by proximity
    seen = []
    for bpt, name, s, sg in sorted(out, key=lambda x: (x[0], -x[3]['nonblank'])):
        if any(bpt == b and abs(s - o) < 0x2000 for b, o in seen): continue
        seen.append((bpt, s))
        print('  %-4s 0x%06X nonblank=%.2f r0b=%.2f r7b=%.2f ink=%.3f pure=%.2f ncol=%d hist=%s'
              % (name, s, sg['nonblank'], sg['row0blank'], sg['row7blank'],
                 sg['ink_ratio'], sg['pure'], sg['ncolors'],
                 {k: v for k, v in sg['hist'].items()}))
    return body

if __name__ == '__main__':
    path = sys.argv[1]; tag = sys.argv[2]
    scan(path, tag)
    print('# -> %s' % tag)