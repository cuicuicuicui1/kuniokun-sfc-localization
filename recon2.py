#!/usr/bin/env python3
"""SFC recon v2: robust Shift-JIS text runs, validated pointer tables, font candidate location."""
import os, sys, zlib, json, struct
from collections import Counter

ROOT = r"F:\BaiduNetdiskDownload\SFC"
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------- Shift-JIS primitives ----------------
def sj_len(b):
    if 0x20 <= b <= 0x7E: return 1          # ASCII
    if 0xA1 <= b <= 0xDF: return 1          # halfwidth kana
    if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC: return 2
    return 0

def sj_trail(b):
    return (0x40 <= b <= 0x7E) or (0x80 <= b <= 0xFC)

def sj_class(b1, b2):
    v = (b1 << 8) | b2
    if 0x829F <= v <= 0x82F1: return 'hira'
    if 0x8340 <= v <= 0x8396: return 'kata'
    if 0x889F <= v <= 0x9872: return 'kanji'
    if 0x8140 <= v <= 0x81AC or 0x81B8 <= v <= 0x81BF: return 'punct'
    return 'other'

def text_runs(data, minchars=6):
    """Linear scan for runs of >= minchars valid Shift-JIS chars."""
    runs = []
    n = len(data)
    i = 0
    while i < n - 1:
        start = i
        chars = []
        j = i
        while j < n - 1:
            L = sj_len(data[j])
            if L == 1:
                chars.append((j, 1, 'ascii')); j += 1
            elif L == 2 and sj_trail(data[j + 1]):
                chars.append((j, 2, sj_class(data[j], data[j + 1]))); j += 2
            else:
                break
        if len(chars) >= minchars:
            kinds = Counter(c[2] for c in chars)
            jp = kinds['hira'] + kinds['kata'] + kinds['kanji']
            runs.append({'start': start, 'end': j, 'nchars': len(chars),
                         'jp_chars': jp, 'kinds': dict(kinds)})
            i = j
        else:
            i += 1
    return runs

# ---------------- address translation ----------------
def to_rom(bank, addr, mapping, romlen):
    m = mapping or ''
    if 'ExHiROM' in m:
        off = (bank & 0x3F) * 0x10000 + addr
        if bank & 0x80: off += 0x400000
    elif 'HiROM' in m:
        off = (bank & 0x3F) * 0x10000 + addr
    else:                                     # LoROM
        off = (bank & 0x7F) * 0x8000 + (addr & 0x7FFF)
    return off if 0 <= off < romlen else None

# ---------------- pointer tables ----------------
def find_ptr_tables(data, step, off_min=0x200):
    """Strictly increasing pointer runs. step=2 -> u16; step=3 -> lo/hi/bank."""
    n = len(data)
    hits = []
    i = off_min
    def get(p):
        if step == 2: return struct.unpack_from('<H', data, p)[0], None
        return data[p] | (data[p + 1] << 8), data[p + 2]
    while i + step * 8 + step < n:
        # pre-filter: 6 strictly increasing
        ok = True
        pv, pb = get(i)
        for k in range(1, 6):
            cv, cb = get(i + k * step)
            if cv <= pv or cv - pv > 0x4000 or (step == 3 and cb != pb):
                ok = False; break
            pv, pb = cv, cb
        if not ok:
            i += step; continue
        pv, pb = get(i)
        j, cnt = i, 1
        while j + 2 * step < n:
            cv, cb = get(j + step)
            if cv <= pv or cv - pv > 0x4000 or (step == 3 and cb != pb):
                break
            pv, pb = cv, cb
            j += step; cnt += 1
        if cnt >= 12:
            hits.append({'offset': i, 'entries': cnt, 'step': step,
                         'bank': pb, 'first': get(i)[0], 'last': pv})
        i = max(i + step, j)
    return hits

def validate_table(tbl, data, mapping, runs_by_start, tol=0x60):
    """Do this table's pointers land on text runs?"""
    starts = set(runs_by_start)
    n = len(data)
    ok = 0; checked = 0; samples = []
    step = tbl['step']
    p = tbl['offset']
    for k in range(min(tbl['entries'], 120)):
        q = p + k * step
        if step == 2:
            lo = struct.unpack_from('<H', data, q)[0]
            # try same bank as table start's natural bank, then adjacent
            base_banks = [tbl['bank_guess']] if tbl.get('bank_guess') is not None else []
            cand = [lo]
            for b in base_banks:
                rb = b
                ro = to_rom(rb, lo, mapping, n)
                if ro is not None: cand.append(ro)
        else:
            lo = data[q] | (data[q + 1] << 8)
            cand = [to_rom(data[q + 2], lo, mapping, n)]
        hit = None
        for c in cand:
            if c is None: continue
            for d in range(-tol, tol + 1):
                if c + d in starts:
                    hit = c + d; break
            if hit is not None: break
        checked += 1
        if hit is not None:
            ok += 1
            if len(samples) < 3:
                samples.append({'ptr': lo, 'rom': '0x%06X' % hit})
    return {'checked': checked, 'on_text': ok,
            'ratio': round(ok / checked, 3) if checked else 0, 'samples': samples}

# ---------------- font candidate detection ----------------
def decode_tile2bpp(d, off):
    """8x8, 2bpp planar, 16 bytes. Returns list of 8 rows of 8 palette indices."""
    px = []
    for r in range(8):
        p0 = d[off + r * 2]; p1 = d[off + r * 2 + 1]
        row = []
        for b in range(8):
            bit = 7 - b
            v = ((p0 >> bit) & 1) | (((p1 >> bit) & 1) << 1)
            row.append(v)
        px.append(row)
    return px

def decode_tile4bpp(d, off):
    """8x8, 4bpp planar, 32 bytes: bytes 0-15 = planes 0/1 interleaved, 16-31 = planes 2/3."""
    px = []
    for r in range(8):
        p0 = d[off + r * 2]; p1 = d[off + r * 2 + 1]
        p2 = d[off + 16 + r * 2]; p3 = d[off + 16 + r * 2 + 1]
        row = []
        for b in range(8):
            bit = 7 - b
            v = ((p0 >> bit) & 1) | (((p1 >> bit) & 1) << 1) \
                | (((p2 >> bit) & 1) << 2) | (((p3 >> bit) & 1) << 3)
            row.append(v)
        px.append(row)
    return px

def tile_stats(px):
    ink = sum(1 for row in px for v in row if v != 0)
    blank_r0 = all(v == 0 for v in px[0])
    blank_r7 = all(v == 0 for v in px[7])
    blank_c0 = all(px[r][0] == 0 for r in range(8))
    blank_c7 = all(px[r][7] == 0 for r in range(8))
    full = sum(1 for row in px for v in row if v != 0) == 64
    return ink / 64.0, blank_r0, blank_r7, blank_c0, blank_c7, full

def score_font_region(data, start, ntiles, bytes_per_tile, dec):
    if start + ntiles * bytes_per_tile > len(data): return None
    inks = []; b0 = 0; br7 = 0; bc0 = 0; bc7 = 0; fulls = 0; nonblank = 0
    for t in range(ntiles):
        px = dec(data, start + t * bytes_per_tile)
        ink, r0, r7, c0, c7, full = tile_stats(px)
        inks.append(ink)
        b0 += r0; br7 += r7; bc0 += c0; bc7 += c7; fulls += full
        if ink > 0: nonblank += 1
    mean_ink = sum(inks) / len(inks)
    return {'mean_ink': mean_ink, 'row0_blank': b0 / ntiles, 'row7_blank': br7 / ntiles,
            'col0_blank': bc0 / ntiles, 'col7_blank': bc7 / ntiles,
            'full_tiles': fulls / ntiles, 'nonblank': nonblank / ntiles}

def find_font_candidates(data, mapping, bpt, dec, ntiles=192, stride=0x800):
    """Score sliding windows; return top candidates."""
    cands = []
    size = ntiles * bpt
    n = len(data)
    s = 0x200
    while s + size <= n:
        win = data[s:s + size]
        # cheap C-level pre-filter: real glyph data is not mostly blanks
        z = win.count(0); f = win.count(0xFF)
        if z > size * 0.35 or f > size * 0.25:
            s += stride; continue
        st = score_font_region(data, s, ntiles, bpt, dec)
        if st:
            # a packed text font: most tiles inked, glyph rows inside a box
            if 0.04 <= st['mean_ink'] <= 0.40 and st['nonblank'] >= 0.85 \
               and st['row0_blank'] >= 0.5 and st['row7_blank'] >= 0.3:
                score = st['nonblank'] * 2 + st['row0_blank'] + st['row7_blank'] - abs(st['mean_ink'] - 0.16) * 4
                cands.append((score, s, st))
        s += stride
    cands.sort(key=lambda c: -c[0])
    # dedupe overlapping
    out = []
    for sc, s, st in cands:
        if any(abs(s - o[1]) < size for o in out): continue
        out.append((sc, s, st))
        if len(out) >= 12: break
    return out

# ---------------- rendering ----------------
def render_tiles(data, start, ntiles, bpt, dec, cols=32, scale=3, path='font.png'):
    from PIL import Image
    rows = (ntiles + cols - 1) // cols
    W, H = cols * 8 * scale, rows * 8 * scale
    img = Image.new('L', (W, H), 255)
    px = img.load()
    pal = {0: 255, 1: 170, 2: 85, 3: 0, 4: 200, 5: 140, 6: 70, 7: 0,
           8: 255, 9: 200, 10: 150, 11: 100, 12: 60, 13: 40, 14: 20, 15: 0}
    for t in range(ntiles):
        off = start + t * bpt
        if off + bpt > len(data): break
        g = dec(data, off)
        cx = (t % cols) * 8 * scale
        cy = (t // cols) * 8 * scale
        for y in range(8):
            for x in range(8):
                v = pal.get(g[y][x], 0)
                for dy in range(scale):
                    for dx in range(scale):
                        px[cx + x * scale + dx, cy + y * scale + dy] = v
    img.save(path)
    return path

# ---------------- per-ROM driver ----------------
MAP_MODES = {0x20:'LoROM', 0x21:'HiROM', 0x22:'S-DD1', 0x23:'SA-1', 0x25:'ExHiROM',
             0x30:'LoROM+Fast', 0x31:'HiROM+Fast', 0x33:'SA-1+Fast', 0x35:'ExHiROM+Fast'}

def analyse(path):
    with open(path, 'rb') as f: raw = f.read()
    ch = 512 if len(raw) % 32768 == 512 else 0
    body = raw[ch:]
    n = len(body)
    out = {'file': os.path.basename(path), 'path': path, 'rom_size': n,
           'file_size': len(raw), 'copier_header': ch,
           'crc32': '%08X' % (zlib.crc32(body) & 0xFFFFFFFF)}
    # header
    hdr = {}
    for label, off in (('LoROM', 0x7FC0), ('HiROM', 0xFFC0)):
        if off + 0x20 > n: continue
        h = body[off:off + 0x20]
        asc = sum(1 for c in h[0:21] if 0x20 <= c < 0x7f)
        try:
            sjt = h[0:21].decode('shift_jis').rstrip()
            sjok = sum(1 for c in sjt if ord(c) > 0x2000)
        except Exception:
            sjt = ''; sjok = 0
        hdr[label] = {'off': off, 'asc': asc, 'sj': sjt, 'sjok': sjok,
                      'map_mode': h[0x15], 'rom_size_byte': h[0x17],
                      'country': h[0x19], 'version': h[0x1B],
                      'checksum': struct.unpack('<H', h[0x1E:0x20])[0]}
    # prefer the mapping whose title is cleanest (ascii or sjis)
    def quality(h): return max(h['asc'], h['sjok'] * 2)
    best_label = max(hdr, key=lambda k: quality(hdr[k])) if hdr else None
    b = hdr.get(best_label, {})
    mapping = MAP_MODES.get(b.get('map_mode', 0), best_label or '?')
    out['header'] = {
        'mapping': mapping, 'map_mode_byte': '%02X' % b.get('map_mode', 0),
        'title_ascii': body[b['off']:b['off'] + 21].decode('ascii', 'replace').rstrip() if b else '',
        'title_sjis': b.get('sj', ''),
        'title_is_sjis': b.get('sjok', 0) > 3,
        'rom_size_byte': '%02X' % b.get('rom_size_byte', 0),
        'country': b.get('country', -1), 'version': b.get('version', -1),
        'checksum_stored': '%04X' % b.get('checksum', 0),
    }
    # checksum
    if b:
        try:
            tot = sum(body) - body[b['off'] + 0x1E] - body[b['off'] + 0x1F] + 0xFF
            if n & (n - 1):
                p = 1
                while p * 2 <= n: p *= 2
                tail = body[p:]; rep = (p // len(tail)) + 1
                tot = sum(body[:p]) + sum((tail * rep)[:p]) - body[b['off'] + 0x1E] - body[b['off'] + 0x1F] + 0xFF
            out['header']['checksum_calc'] = '%04X' % (tot & 0xFFFF)
            out['header']['checksum_ok'] = (tot & 0xFFFF) == b['checksum']
        except Exception:
            out['header']['checksum_ok'] = 'err'

    # free space
    runs_free = []
    i = 0x200
    while i < n:
        if body[i] in (0x00, 0xFF):
            j = i
            while j < n and body[j] == body[i]: j += 1
            if j - i >= 0x400: runs_free.append((i, j - i, '00' if body[i] == 0 else 'FF'))
            i = j
        else: i += 1
    out['free_total'] = sum(r[1] for r in runs_free)
    out['free_top'] = [{'off': '0x%06X' % r[0], 'size': r[1], 'fill': r[2]}
                       for r in sorted(runs_free, key=lambda r: -r[1])[:6]]

    # text runs
    tr = text_runs(body, 8)
    jp = [r for r in tr if r['jp_chars'] >= 6]
    out['text_runs_total'] = len(tr)
    out['text_runs_jp'] = len(jp)
    out['jp_chars_total'] = sum(r['jp_chars'] for r in jp)
    out['jp_chars_in_runs'] = sum(r['nchars'] for r in jp)
    kinds = Counter()
    for r in jp: kinds.update(r['kinds'])
    out['char_kinds'] = dict(kinds)
    by_size = Counter()
    for r in jp: by_size[min(r['nchars'] // 8 * 8, 128)] += 1
    out['run_len_hist'] = dict(sorted(by_size.items()))
    hot = {}
    for r in jp:
        blk = (r['start'] // 0x8000) * 0x8000
        hot[blk] = hot.get(blk, 0) + r['jp_chars']
    out['text_hot'] = [{'off': '0x%06X' % k, 'jp_chars': v}
                       for k, v in sorted(hot.items(), key=lambda kv: -kv[1])[:8]]
    # total text bytes covered
    out['text_bytes_covered'] = sum(r['end'] - r['start'] for r in jp)
    # table candidates
    tbls = find_ptr_tables(body, 2)
    for t in tbls: t['kind'] = 'u16'
    t3 = find_ptr_tables(body, 3)
    for t in t3: t['kind'] = 'u24'
    allt = tbls + t3
    allt = [t for t in allt if t['entries'] >= 20]
    # annotate bank guess from a text-heavy bank
    by_start = {}
    for r in jp: by_start[r['start']] = r
    for t in allt:
        # guess bank by majority of u16 high bytes in the table's neighbourhood
        t['bank_guess'] = (t['offset'] // 0x8000) & 0x7F if 'LoROM' in mapping else ((t['offset'] // 0x10000) & 0x3F)
    scored = []
    for t in allt[:300]:
        v = validate_table(t, body, mapping, by_start)
        t.update(v)
        if v['checked'] >= 10 and v['ratio'] >= 0.5:
            scored.append(t)
    scored.sort(key=lambda t: -t['entries'])
    out['ptr_tables_validated'] = [{'off': '0x%06X' % t['offset'], 'entries': t['entries'],
                                    'kind': t['kind'], 'on_text': t['on_text'],
                                    'ratio': t['ratio'], 'samples': t['samples']}
                                   for t in scored[:10]]
    out['ptr_candidates_raw'] = len(allt)
    out['ptr_validated_count'] = len(scored)

    # font candidates
    fc2 = find_font_candidates(body, mapping, 16, decode_tile2bpp)
    fc4 = find_font_candidates(body, mapping, 32, decode_tile4bpp)
    out['font_cands_2bpp'] = [{'off': '0x%06X' % s, 'score': round(sc, 2),
                               'ink': round(st['mean_ink'], 3), 'nonblank': round(st['nonblank'], 2),
                               'r0blank': round(st['row0_blank'], 2)} for sc, s, st in fc2[:5]]
    out['font_cands_4bpp'] = [{'off': '0x%06X' % s, 'score': round(sc, 2),
                               'ink': round(st['mean_ink'], 3), 'nonblank': round(st['nonblank'], 2),
                               'r0blank': round(st['row0_blank'], 2)} for sc, s, st in fc4[:5]]
    return out, body, mapping

def main():
    targets = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')): targets.append(os.path.join(dp, f))
    targets.sort()
    res = []
    for t in targets:
        try:
            o, body, mapping = analyse(t)
            res.append(o)
            print('=' * 76)
            print(os.path.relpath(t, ROOT))
            h = o['header']
            print('  %s | size=%d | hdr=%d | crc32=%s | title=%r%s' % (
                h['mapping'], o['rom_size'], o['copier_header'], o['crc32'],
                h['title_ascii'], '  [SJIS title: %r]' % h['title_sjis'] if h['title_is_sjis'] else ''))
            print('  checksum ok=%s (stored=%s calc=%s)  free>=1K: %d B  top=%s' % (
                h.get('checksum_ok'), h['checksum_stored'], h.get('checksum_calc'),
                o['free_total'], ', '.join('%s(%d,%s)' % (f['off'], f['size'], f['fill']) for f in o['free_top'][:3])))
            print('  SJIS runs>=8: %d (JP-bearing %d) | jp chars in runs=%d | bytes=%d' % (
                o['text_runs_total'], o['text_runs_jp'], o['jp_chars_in_runs'], o['text_bytes_covered']))
            print('  kinds=%s' % o['char_kinds'])
            print('  hot: %s' % ', '.join('%s:%d' % (b['off'], b['jp_chars']) for b in o['text_hot'][:5]))
            print('  ptr: raw=%d validated=%d %s' % (
                o['ptr_candidates_raw'], o['ptr_validated_count'],
                '| ' + '; '.join('%s %s ent=%d ontext=%d r=%s' % (p['off'], p['kind'], p['entries'], p['on_text'], p['ratio'])
                                 for p in o['ptr_tables_validated'][:3]) if o['ptr_tables_validated'] else ''))
            print('  font2bpp: %s' % ', '.join('%s sc=%.1f ink=%.3f nb=%.2f' % (c['off'], c['score'], c['ink'], c['nonblank']) for c in o['font_cands_2bpp'][:3]))
            print('  font4bpp: %s' % ', '.join('%s sc=%.1f ink=%.3f nb=%.2f' % (c['off'], c['score'], c['ink'], c['nonblank']) for c in o['font_cands_4bpp'][:3]))
        except Exception as e:
            import traceback; traceback.print_exc()
            res.append({'path': t, 'error': str(e)})
    with open(os.path.join(HERE, 'recon2.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('\nJSON -> recon2.json')

if __name__ == '__main__':
    main()