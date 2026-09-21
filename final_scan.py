#!/usr/bin/env python3
"""Comprehensive recon: font pages via 2-colour 2bpp signature + text systems + free space.
Produces a JSON + a per-ROM font montage PNG for visual confirmation."""
import os, sys, zlib, struct, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon2 import (text_runs, find_ptr_tables, MAP_MODES, decode_tile2bpp,
                    decode_tile4bpp, render_tiles, sj_len, sj_trail)

ROOT = r"F:\BaiduNetdiskDownload\SFC"
HERE = os.path.dirname(os.path.abspath(__file__))

def font_pages(body, min_run=4):
    """Find contiguous runs of 1KB windows that look like a 2-colour 2bpp bitmap font."""
    W = 0x400                      # 1KB = 64 tiles
    good = []
    for s in range(0, len(body) - W, 0x200):
        win = body[s:s + W]
        z = win.count(0)
        if z > W * 0.45 or z < W * 0.02: continue
        eq = sum(1 for i in range(0, W, 2) if win[i] == win[i + 1])
        if eq < (W // 2) * 0.80: continue
        # a real font: most 16-byte tiles have some ink, and top row is often blank
        nb = 0; r0b = 0; nt = W // 16
        for t in range(nt):
            o = s + t * 16
            t0 = body[o:o + 2]; t7 = body[o + 14:o + 16]
            if body[o:o + 16] != b'\x00' * 16: nb += 1
            if t0 == b'\x00\x00': r0b += 1
        if nb / nt < 0.75: continue
        good.append((s, eq / (W // 2), nb / nt, r0b / nt))
    # merge overlapping windows into regions
    regions = []
    for s, eqr, nbr, r0b in good:
        if regions and s - regions[-1][1] <= 0x600:
            regions[-1][1] = s + W
            regions[-1][2].append((s, eqr, nbr, r0b))
        else:
            regions.append([s, s + W, [(s, eqr, nbr, r0b)]])
    out = []
    for a, b, items in regions:
        if b - a < min_run * 0x400: continue
        out.append({'start': '0x%06X' % a, 'end': '0x%06X' % b, 'bytes': b - a,
                    'tiles': (b - a) // 16,
                    'eq': round(sum(i[1] for i in items) / len(items), 3),
                    'nonblank': round(sum(i[2] for i in items) / len(items), 3),
                    'r0blank': round(sum(i[3] for i in items) / len(items), 3)})
    out.sort(key=lambda r: -r['bytes'])
    return out

def byte_hist_blocks(body, blk=0x2000):
    dens = []
    for s in range(0, len(body) - blk, blk):
        w = body[s:s + blk]
        z = w.count(0)
        dens.append((s, z))
    return dens

def lowentropy_runs(body, blk=0x800):
    """Regions with few distinct byte values (possible single-byte-code text or tables)."""
    out = []
    for s in range(0, len(body) - blk, blk):
        w = body[s:s + blk]
        n = len(set(w))
        if n <= 96:
            out.append((s, n, w.count(0)))
    return out

def analyse(path):
    raw = open(path, 'rb').read()
    ch = 512 if len(raw) % 32768 == 512 else 0
    body = raw[ch:]
    n = len(body)
    r = {'file': os.path.basename(path), 'size': n, 'copier': ch,
         'crc32': '%08X' % (zlib.crc32(body) & 0xFFFFFFFF)}
    # header / mapping
    best = None
    for label, off in (('LoROM', 0x7FC0), ('HiROM', 0xFFC0)):
        if off + 0x20 > n: continue
        h = body[off:off + 0x20]
        asc = sum(1 for c in h[0:21] if 0x20 <= c < 0x7f)
        try:
            s = h[0:21].decode('shift_jis').rstrip(); sjok = sum(1 for c in s if ord(c) > 0x2000)
        except Exception:
            s = ''; sjok = 0
        q = max(asc, sjok * 2)
        if best is None or q > best[0]: best = (q, label, off, h, s, asc, sjok)
    q, label, off, h, s, asc, sjok = best
    r['mapping'] = MAP_MODES.get(h[0x15], label)
    r['map_mode'] = '%02X' % h[0x15]
    r['title'] = h[0:21].decode('ascii', 'replace').rstrip()
    r['title_sjis'] = s
    r['title_is_sjis'] = sjok > 3
    r['rom_size_byte'] = '%02X' % h[0x17]
    r['declared_mbit'] = {0x08: 2, 0x09: 4, 0x0A: 8, 0x0B: 16, 0x0C: 32, 0x0D: 64}.get(h[0x17], '?')
    # free space
    free = []
    i = 0x200
    while i < n:
        if body[i] in (0x00, 0xFF):
            j = i
            while j < n and body[j] == body[i]: j += 1
            if j - i >= 0x800: free.append((i, j - i, '00' if body[i] == 0 else 'FF'))
            i = j
        else: i += 1
    r['free_total'] = sum(f[1] for f in free)
    r['free_top'] = [{'off': '0x%06X' % f[0], 'size': f[1], 'fill': f[2]}
                     for f in sorted(free, key=lambda f: -f[1])[:5]]
    # text
    tr = text_runs(body, 8)
    jp = [x for x in tr if x['jp_chars'] >= 6]
    r['sjis_runs'] = len(tr)
    r['sjis_jp_runs'] = len(jp)
    r['sjis_jp_chars'] = sum(x['jp_chars'] for x in jp)
    r['sjis_bytes_covered'] = sum(x['end'] - x['start'] for x in jp)
    k = Counter()
    for x in jp: k.update(x['kinds'])
    r['kinds'] = dict(k)
    r['longest_runs'] = [{'n': x['nchars'], 'off': '0x%06X' % x['start']}
                         for x in sorted(jp, key=lambda x: -x['nchars'])[:5]]
    hot = Counter()
    for x in jp: hot[x['start'] // 0x8000 * 0x8000] += x['jp_chars']
    r['text_hot'] = ['0x%06X:%d' % (a, b) for a, b in hot.most_common(6)]
    # fonts
    r['font_pages'] = font_pages(body)[:6]
    # pointer tables
    tl = []
    for step in (2, 3):
        ts = [t for t in find_ptr_tables(body, step) if t['entries'] >= 24]
        ts.sort(key=lambda t: -t['entries'])
        for t in ts[:3]:
            tl.append({'off': '0x%06X' % t['offset'], 'n': t['entries'], 'step': step})
    r['ptr_cands'] = tl
    return r, body

def montage(body, pages, tag, maxpages=3, ntiles=192, scale=3, cols=16):
    from PIL import Image
    imgs = []
    for i, pg in enumerate(pages[:maxpages]):
        s = int(pg['start'], 16)
        p = os.path.join(HERE, 'm_%s_%d.png' % (tag, i))
        render_tiles(body, s, ntiles, 16, decode_tile2bpp, cols=cols, scale=scale, path=p)
        imgs.append(p)
    return imgs

def main():
    targets = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')): targets.append(os.path.join(dp, f))
    targets.sort()
    res = []
    for t in targets:
        try:
            r, body = analyse(t)
            tag = ''.join(c for c in os.path.basename(t) if c.isalnum())[:12]
            r['tag'] = tag
            if r['font_pages']:
                r['montages'] = montage(body, r['font_pages'], tag)
            res.append(r)
            print('=' * 78)
            print('%-52s %s %s size=%d crc=%s' % (os.path.basename(t)[:52], r['mapping'], r['rom_size_byte'], r['size'], r['crc32']))
            print('   title=%r sjis=%r(%s)' % (r['title'], r['title_sjis'], r['title_is_sjis']))
            print('   SJIS runs>=8: %d, jp runs %d, jp chars %d, covered %d B (%.2f%%)  kinds=%s'
                  % (r['sjis_runs'], r['sjis_jp_runs'], r['sjis_jp_chars'], r['sjis_bytes_covered'],
                     100.0 * r['sjis_bytes_covered'] / r['size'], r['kinds']))
            print('   longest: %s' % r['longest_runs'])
            print('   free>=2K: %d B  %s' % (r['free_total'], r['free_top']))
            for f in r['font_pages']:
                print('   FONT %s..%s %d B (%d tiles) eq=%s nonblank=%s r0blank=%s'
                      % (f['start'], f['end'], f['bytes'], f['tiles'], f['eq'], f['nonblank'], f['r0blank']))
            if not r['font_pages']: print('   FONT: none detected')
            print('   ptr cands: %s' % r['ptr_cands'])
        except Exception as e:
            import traceback; traceback.print_exc()
    with open(os.path.join(HERE, 'final.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('\n-> final.json')

if __name__ == '__main__':
    main()