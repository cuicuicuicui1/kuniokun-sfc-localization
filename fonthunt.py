#!/usr/bin/env python3
"""Broad font hunt: detect 2-colour glyph tables for both 2bpp and 4bpp storage."""
import os, sys, zlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon2 import render_tiles, decode_tile2bpp, decode_tile4bpp

ROOT = r"F:\BaiduNetdiskDownload\SFC"
HERE = os.path.dirname(os.path.abspath(__file__))

def scan2bpp(body, W=0x400):
    """.sfc 2bpp: plane0/plane1 interleaved as byte pairs -> equal pairs = 2-colour."""
    out = []
    step = 0x100
    for s in range(0, len(body) - W, step):
        w = body[s:s + W]
        z = w.count(0)
        if z > W * 0.5 or z < W * 0.03: continue
        eq = sum(1 for i in range(0, W, 2) if w[i] == w[i + 1]) / (W // 2)
        if eq < 0.65: continue
        nt = W // 16
        nb = sum(1 for t in range(nt) if body[s + t*16:s + t*16 + 16] != b'\x00' * 16) / nt
        r0 = sum(1 for t in range(nt) if body[s + t*16:s + t*16 + 2] == b'\x00\x00') / nt
        r7 = sum(1 for t in range(nt) if body[s + t*16 + 14:s + t*16 + 16] == b'\x00\x00') / nt
        if nb < 0.6: continue
        out.append((s, eq, nb, r0, r7))
    return out

def scan4bpp(body, W=0x800):
    """4bpp: 32-byte tile, planes 0/1 as pairs 0-15, planes 2/3 as pairs 16-31."""
    out = []
    step = 0x100
    for s in range(0, len(body) - W, step):
        w = body[s:s + W]
        z = w.count(0)
        if z > W * 0.5 or z < W * 0.03: continue
        nt = W // 32
        ok = 0; nb = 0; r0 = 0; r7 = 0
        for t in range(nt):
            o = s + t * 32
            if o + 32 > len(body): break
            t32 = body[o:o + 32]
            a = all(t32[2*r] == t32[2*r + 1] for r in range(8))
            b = all(t32[16 + 2*r] == t32[16 + 2*r + 1] for r in range(8))
            if a and b: ok += 1
            if t32 != b'\x00' * 32: nb += 1
            if t32[0:2] == b'\x00\x00': r0 += 1
            if t32[14:16] == b'\x00\x00' or t32[30:32] == b'\x00\x00': r7 += 1
        ok /= nt; nb /= nt; r0 /= nt; r7 /= nt
        if ok < 0.65 or nb < 0.6: continue
        out.append((s, ok, nb, r0, r7))
    return out

def merge(hits, win, gap=0x400):
    regions = []
    for s, eq, nb, r0, r7 in hits:
        if regions and s - regions[-1][1] <= gap:
            regions[-1][1] = max(regions[-1][1], s + win)
            regions[-1][2].append((eq, nb, r0, r7))
        else:
            regions.append([s, s + win, [(eq, nb, r0, r7)]])
    out = []
    for a, b, items in regions:
        out.append({'start': a, 'end': b, 'bytes': b - a, 'tiles': (b - a) // 16,
                    'eq': round(sum(i[0] for i in items) / len(items), 3),
                    'nonblank': round(sum(i[1] for i in items) / len(items), 3),
                    'r0blank': round(sum(i[2] for i in items) / len(items), 3),
                    'r7blank': round(sum(i[3] for i in items) / len(items), 3)})
    out.sort(key=lambda r: -r['bytes'])
    return out

def main():
    targets = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')): targets.append(os.path.join(dp, f))
    targets.sort()
    allres = []
    for t in targets:
        raw = open(t, 'rb').read()
        ch = 512 if len(raw) % 32768 == 512 else 0
        body = raw[ch:]
        tag = ''.join(c for c in os.path.basename(t) if c.isalnum())[:10]
        r2 = merge(scan2bpp(body), 0x400)
        r4 = merge(scan4bpp(body), 0x800)
        print('=' * 78)
        print('%s  (%d B)  crc=%08X' % (os.path.basename(t), len(body), zlib.crc32(body) & 0xFFFFFFFF))
        for name, rs, bpt, dec in (('2bpp', r2, 16, decode_tile2bpp), ('4bpp', r4, 32, decode_tile4bpp)):
            real = [x for x in rs if x['bytes'] >= 0x400]
            print('  %s regions>=1K: %d  top:' % (name, len(real)))
            for x in real[:4]:
                print('     0x%06X..0x%06X %6d B %4d tiles eq=%.2f nb=%.2f r0b=%.2f r7b=%.2f'
                      % (x['start'], x['end'], x['bytes'], x['tiles'], x['eq'], x['nonblank'], x['r0blank'], x['r7blank']))
            for i, x in enumerate(real[:2]):
                p = os.path.join(HERE, 'F_%s_%s_%d.png' % (tag, name, i))
                render_tiles(body, x['start'], 200, bpt, dec, cols=20, scale=3, path=p)
                print('       -> %s' % os.path.basename(p))
        allres.append({'file': os.path.basename(t), 'tag': tag, '2bpp': r2[:4], '4bpp': r4[:4]})
    json.dump(allres, open(os.path.join(HERE, 'fonts.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()