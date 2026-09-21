#!/usr/bin/env python3
"""Focused per-ROM analysis: decoded text samples + font rendering."""
import os, sys, zlib, struct
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon2 import (text_runs, to_rom, find_font_candidates, decode_tile2bpp,
                    decode_tile4bpp, render_tiles, MAP_MODES, find_ptr_tables)

HERE = os.path.dirname(os.path.abspath(__file__))

def load(path):
    raw = open(path, 'rb').read()
    ch = 512 if len(raw) % 32768 == 512 else 0
    return raw[ch:], ch

def header(body):
    best = None
    for label, off in (('LoROM', 0x7FC0), ('HiROM', 0xFFC0)):
        if off + 0x20 > len(body): continue
        h = body[off:off+0x20]
        asc = sum(1 for c in h[0:21] if 0x20 <= c < 0x7f)
        try:
            s = h[0:21].decode('shift_jis').rstrip()
            sjok = sum(1 for c in s if ord(c) > 0x2000)
        except Exception:
            s = ''; sjok = 0
        q = max(asc, sjok*2)
        if best is None or q > best[0]:
            best = (q, label, off, h, s, asc, sjok)
    if not best: return None
    q, label, off, h, s, asc, sjok = best
    return {'label': label, 'mapping': MAP_MODES.get(h[0x15], label),
            'map_mode': '%02X' % h[0x15], 'title_ascii': h[0:21].decode('ascii','replace').rstrip(),
            'title_sjis': s, 'rom_size_byte': '%02X' % h[0x17],
            'checksum': '%04X' % struct.unpack('<H', h[0x1E:0x20])[0]}

def dump_text(body, lo, hi, maxs=25):
    n = 0
    i = lo
    while i < hi and n < maxs:
        L2 = 24
        seg = body[i:i+L2]
        # find a long-ish run
        runs = text_runs(seg, 6)
        if runs:
            r = max(runs, key=lambda r: r['nchars'])
            s = seg[r['start']:r['end']]
            try: t = s.decode('shift_jis')
            except Exception: t = ''
            if t:
                print('  0x%06X %s' % (i + r['start'], t))
                n += 1
                i += r['end'] + 1
                continue
        i += 1
    return n

def main(path, tag):
    body, ch = load(path)
    print('#' * 78)
    print('# %s' % os.path.basename(path), 'size=%d hdr=%d crc=%08X' % (len(body), ch, zlib.crc32(body) & 0xFFFFFFFF))
    h = header(body)
    print('# hdr=%s' % h)
    mapping = h['mapping']
    tr = text_runs(body, 8)
    jp = [r for r in tr if r['jp_chars'] >= 6]
    print('# text runs >=8 chars: %d | jp-bearing: %d | jp chars: %d | bytes covered: %d (%.1f%%)'
          % (len(tr), len(jp), sum(r['jp_chars'] for r in jp),
             sum(r['end']-r['start'] for r in jp), 100.0*sum(r['end']-r['start'] for r in jp)/len(body)))
    hot = {}
    for r in jp: hot[r['start']//0x4000] = hot.get(r['start']//0x4000, 0) + r['jp_chars']
    top = sorted(hot.items(), key=lambda kv: -kv[1])[:12]
    print('# hot 16K blocks: %s' % ', '.join('0x%06X:%d' % (k*0x4000, v) for k, v in top))
    lens = Counter()
    for r in jp: lens[min(r['nchars'], 200)] += 1
    print('# longest runs: %s' % [(r['nchars'], '0x%06X' % r['start']) for r in sorted(jp, key=lambda r: -r['nchars'])[:8]])
    print('# --- decoded text samples (dense regions) ---')
    for k, v in top[:6]:
        print(' # block 0x%06X (jp chars %d)' % (k*0x4000, v))
        dump_text(body, k*0x4000, min(k*0x4000+0x8000, len(body)), 12)
    # font candidates
    print('# --- font candidates ---')
    fc2 = find_font_candidates(body, mapping, 16, decode_tile2bpp, ntiles=128, stride=0x400)
    fc4 = find_font_candidates(body, mapping, 32, decode_tile4bpp, ntiles=128, stride=0x400)
    for i, (sc, s, st) in enumerate(fc2[:6]):
        p = os.path.join(HERE, 'font_%s_2bpp_%d.png' % (tag, i))
        render_tiles(body, s, 256, 16, decode_tile2bpp, cols=32, scale=3, path=p)
        print('  2bpp #%d off=0x%06X score=%.2f ink=%.3f nonblank=%.2f r0b=%.2f -> %s'
              % (i, s, sc, st['mean_ink'], st['nonblank'], st['row0_blank'], os.path.basename(p)))
    for i, (sc, s, st) in enumerate(fc4[:6]):
        p = os.path.join(HERE, 'font_%s_4bpp_%d.png' % (tag, i))
        render_tiles(body, s, 256, 32, decode_tile4bpp, cols=32, scale=3, path=p)
        print('  4bpp #%d off=0x%06X score=%.2f ink=%.3f nonblank=%.2f r0b=%.2f -> %s'
              % (i, s, sc, st['mean_ink'], st['nonblank'], st['row0_blank'], os.path.basename(p)))
    # pointer tables (u16 lo/hi + u24) restricted to a reasonable cost
    print('# --- pointer tables ---')
    for step, kind in ((2, 'u16'), (3, 'u24lo')):
        ts = [t for t in find_ptr_tables(body, step) if t['entries'] >= 24]
        ts.sort(key=lambda t: -t['entries'])
        print('  step=%d candidates(>=24): %d  top: %s' % (
            step, len(ts), ', '.join('0x%06X(n=%d)' % (t['offset'], t['entries']) for t in ts[:6])))
    return body, mapping

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])