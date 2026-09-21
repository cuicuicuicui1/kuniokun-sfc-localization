#!/usr/bin/env python3
"""SFC ROM reconnaissance: header, checksum, free space, text & pointer-table survey."""
import os, sys, zlib, hashlib, json, struct, re
from collections import Counter

ROOT = r"F:\BaiduNetdiskDownload\SFC"

def rom_bytes(path):
    with open(path, 'rb') as f:
        return f.read()

def detect_copier_header(data):
    """512-byte copier header makes size ≡ 512 (mod 32768)."""
    if len(data) % 32768 == 512:
        return 512
    return 0

def read_header(data, off):
    if off + 0x20 > len(data):
        return None
    h = data[off:off + 0x20]
    name = h[0:21].decode('ascii', 'replace').rstrip()
    # internal name must be mostly printable
    printable = sum(1 for c in h[0:21] if 0x20 <= c < 0x7f)
    return {
        'name': name,
        'printable': printable,
        'map_mode': h[0x15],
        'cart_type': h[0x16],
        'rom_size_byte': h[0x17],
        'sram_size': h[0x18],
        'country': h[0x19],
        'licensee': h[0x1A],
        'version': h[0x1B],
        'checksum_comp': struct.unpack('<H', h[0x1C:0x1E])[0],
        'checksum': struct.unpack('<H', h[0x1E:0x20])[0],
    }

MAP_MODES = {0x20:'LoROM', 0x21:'HiROM', 0x22:'S-DD1', 0x23:'SA-1', 0x25:'ExHiROM',
             0x30:'LoROM+Fast', 0x31:'HiROM+Fast', 0x32:'S-DD1+Fast', 0x33:'SA-1+Fast',
             0x35:'ExHiROM+Fast', 0x34:'SA-1+Fast'}
ROM_SIZES = {0x08:'2Mbit/256K', 0x09:'4Mbit/512K', 0x0A:'8Mbit/1M', 0x0B:'16Mbit/2M',
             0x0C:'32Mbit/4M', 0x0D:'64Mbit/8M'}
COUNTRIES = {0x00:'Japan', 0x01:'USA', 0x02:'Europe', 0x03:'Sweden', 0x06:'France',
             0x07:'Netherlands', 0x09:'Spain', 0x0A:'Germany', 0x0B:'Italy', 0x0D:'South Korea',
             0x0F:'Australia', 0x11:'Brazil', 0x0C:'China'}

def snes_checksum(data, hdr_off):
    """Standard SNES checksum with mirroring for non-power-of-2 sizes."""
    n = len(data)
    if n & (n - 1):                      # not a power of two
        p = 1
        while p * 2 <= n:
            p *= 2
        tail = data[p:n]
        region = bytearray(data[:p])
        # mirror tail into the upper part repeatedly
        pos = p - len(tail)
        body = bytearray(data[:p])
        rep = (p // len(tail)) + 1
        mirrored = (tail * rep)[:p]
        total = sum(body) + sum(mirrored) - (body[0x1E] + body[0x1F]) + 0xFF + 0x00
        return total & 0xFFFF, region
    total = sum(data) - (data[hdr_off + 0x1E] + data[hdr_off + 0x1F]) + 0xFF + 0x00
    return total & 0xFFFF, None

# ---------- Shift-JIS / text density ----------
HIRA = range(0x82A0, 0x82F2)
KATA = range(0x8340, 0x8397)
SJIS_LEAD = set(list(range(0x81, 0xA0)) + list(range(0xE0, 0xFD)))

def sjis_scan(data, offset):
    """Return (hiragana_count, katakana_count, kanji_count) past a 512B header at `offset`."""
    hi = ka = kj = 0
    for i in range(offset, len(data) - 1):
        b = data[i]
        if b not in SJIS_LEAD:
            continue
        v = (b << 8) | data[i + 1]
        if v in HIRA: hi += 1
        elif v in KATA: ka += 1
        elif 0x889F <= v <= 0x9872: kj += 1
    return hi, ka, kj

def sjis_density_map(data, offset, block=0x8000):
    """Per-32KB-block Shift-JIS char count -> heat map."""
    out = []
    for start in range(offset, len(data) - 1, block):
        end = min(start + block, len(data) - 1)
        c = 0
        for i in range(start, end):
            b = data[i]
            if b not in SJIS_LEAD:
                continue
            v = (b << 8) | data[i + 1]
            if v in HIRA or v in KATA or (0x889F <= v <= 0x9872):
                c += 1
        out.append((start, c))
    return out

# ---------- free space ----------
def free_space(data, offset, minrun=0x400):
    runs = []
    n = len(data)
    i = offset
    while i < n:
        if data[i] in (0x00, 0xFF):
            b = data[i]
            j = i
            while j < n and data[j] == b:
                j += 1
            if j - i >= minrun:
                runs.append((i, j - i, '0x00' if b == 0 else '0xFF'))
            i = j
        else:
            i += 1
    return runs

# ---------- pointer table detection ----------
def _mono_ok(data, i, step, order):
    for k in range(1, 5):                       # cheap pre-filter
        if order == 'u16':
            a = struct.unpack_from('<H', data, i + (k - 1) * 2)[0]
            b = struct.unpack_from('<H', data, i + k * 2)[0]
            if not (0 <= b - a <= 0x1200):
                return False
        else:
            a, ab = _v3(data, i + (k - 1) * 3, order)
            b, bb = _v3(data, i + k * 3, order)
            if not (0 <= b - a <= 0x1200 and ab == bb):
                return False
    return True

def _v3(data, p, order):
    a, b, c = data[p], data[p+1], data[p+2]
    if order == 'lo_hi_bank': return a | (b << 8), c
    if order == 'bank_lo_hi': return b | (c << 8), a
    return c | (b << 8), a                      # hi_lo_bank

def find_pointer_tables(data, offset, minrun=24, step=2):
    """Runs of >=minrun monotonically increasing little-endian u16."""
    hits = []
    n = len(data)
    i = offset
    while i + minrun * 2 + 2 < n:
        if not _mono_ok(data, i, step, 'u16'):
            i += 2
            continue
        pv = struct.unpack_from('<H', data, i)[0]
        j, cnt = i, 1
        while j + 4 < n:
            cv = struct.unpack_from('<H', data, j + 2)[0]
            if not (0 <= cv - pv <= 0x1200):
                break
            pv = cv
            j += 2
            cnt += 1
        if cnt >= minrun:
            hits.append((i, cnt))
        i = max(i + 2, j)
    return hits

def find_pointer_tables3(data, offset, minrun=24, maxdelta=0x1200):
    """3-byte pointers, common SFC orders: lo,hi,bank | bank,lo,hi | hi,lo,bank."""
    res = {}
    n = len(data)
    for order in ('lo_hi_bank', 'bank_lo_hi', 'hi_lo_bank'):
        hits = []
        i = offset
        while i + minrun * 3 + 3 < n:
            if not _mono_ok(data, i, 3, order):
                i += 3
                continue
            pv, pb = _v3(data, i, order)
            j, cnt = i, 1
            while j + 6 < n:
                cv, cb = _v3(data, j + 3, order)
                if not (0 <= cv - pv <= maxdelta and cb == pb):
                    break
                pv, pb = cv, cb
                j += 3
                cnt += 1
            if cnt >= minrun:
                hits.append((i, cnt))
            i = max(i + 3, j)
        res[order] = hits
    return res

# ---------- byte-value histogram (1-byte vs 2-byte charset hint) ----------
def byte_profile(data, start, end):
    c = Counter(data[start:end])
    return c

def analyse(path):
    data = rom_bytes(path)
    raw = len(data)
    ch = detect_copier_header(data)
    body = data[ch:]
    out = {
        'file': os.path.basename(path),
        'path': path,
        'file_size': raw,
        'copier_header': ch,
        'rom_size': len(body),
        'crc32': '%08X' % (zlib.crc32(body) & 0xFFFFFFFF),
        'md5': hashlib.md5(body).hexdigest(),
        'sha1': hashlib.sha1(body).hexdigest(),
    }
    cands = []
    for label, off in (('LoROM', 0x7FC0), ('HiROM', 0xFFC0)):
        h = read_header(data, ch + off)
        if h:
            h['offset'] = ch + off
            h['mapping'] = label
            cands.append(h)
    best = max(cands, key=lambda h: h['printable']) if cands else None
    if best:
        out['header'] = {
            'mapping_guess': best['mapping'],
            'internal_title': best['name'],
            'map_mode_byte': '%02X' % best['map_mode'],
            'map_mode': MAP_MODES.get(best['map_mode'], 'unknown'),
            'cart_type': '%02X' % best['cart_type'],
            'rom_size_byte': '%02X' % best['rom_size_byte'],
            'declared_size': ROM_SIZES.get(best['rom_size_byte'], '?'),
            'sram': '%02X' % best['sram_size'],
            'country': COUNTRIES.get(best['country'], 'unknown(%02X)' % best['country']),
            'version': best['version'],
            'checksum_stored': '%04X' % best['checksum'],
            'checksum_complement': '%04X' % best['checksum_comp'],
        }
        # checksum verification (header-relative offsets are already in `body` space)
        n = len(body)
        if n & (n - 1) == 0:
            total = sum(body)
            total -= body[best['offset'] - ch + 0x1E] + body[best['offset'] - ch + 0x1F]
            total += 0xFF + 0x00
            out['header']['checksum_calc'] = '%04X' % (total & 0xFFFF)
            out['header']['checksum_ok'] = (total & 0xFFFF) == best['checksum']
        else:
            p = 1
            while p * 2 <= n:
                p *= 2
            tail = body[p:]
            rep = (p // len(tail)) + 1
            mirrored = (tail * rep)[:p]
            total = sum(body[:p]) + sum(mirrored)
            total -= body[best['offset'] - ch + 0x1E] + body[best['offset'] - ch + 0x1F]
            total += 0xFF + 0x00
            out['header']['checksum_calc'] = '%04X' % (total & 0xFFFF)
            out['header']['checksum_ok'] = (total & 0xFFFF) == best['checksum']
            out['header']['non_power_of_two'] = 'mirrored: %d -> %d (tail %d)' % (n, p, len(tail))
        if best['map_mode'] not in MAP_MODES:
            out['header']['map_mode_warning'] = 'non-standard map mode byte'
    else:
        out['header'] = None

    # free space
    runs = free_space(body, 0x200, 0x400)
    out['free_space_total'] = sum(r[1] for r in runs)
    out['free_space_top'] = [{'offset': '%06X' % r[0], 'size': r[1], 'fill': r[2]}
                             for r in sorted(runs, key=lambda r: -r[1])[:8]]

    # Shift-JIS
    hi, ka, kj = sjis_scan(body, 0)
    out['sjis'] = {'hiragana': hi, 'katakana': ka, 'kanji': kj,
                   'total': hi + ka + kj}
    dm = sjis_density_map(body, 0)
    top = sorted(dm, key=lambda t: -t[1])[:10]
    out['sjis_hot_blocks'] = [{'offset': '%06X' % o, 'count': c} for o, c in top if c > 50]

    # pointer tables
    pt2 = find_pointer_tables(body, 0x200)
    out['ptr2_count'] = len(pt2)
    out['ptr2_top'] = [{'offset': '%06X' % o, 'entries': c} for o, c in
                       sorted(pt2, key=lambda t: -t[1])[:10]]
    pt3 = find_pointer_tables3(body, 0x200)
    out['ptr3_count'] = sum(len(v) for v in pt3.values())
    out['ptr3_top'] = []
    for order, hits in pt3.items():
        for o, c in sorted(hits, key=lambda t: -t[1])[:4]:
            out['ptr3_top'].append({'offset': '%06X' % o, 'entries': c, 'order': order})
    out['ptr3_top'] = sorted(out['ptr3_top'], key=lambda d: -d['entries'])[:8]
    return out

def main():
    targets = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        for fn in filenames:
            if fn.lower().endswith(('.sfc', '.smc')):
                targets.append(os.path.join(dirpath, fn))
    targets.sort()
    results = []
    for t in targets:
        try:
            results.append(analyse(t))
        except Exception as e:
            results.append({'path': t, 'error': '%s: %s' % (type(e).__name__, e)})
    outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recon.json')
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    for r in results:
        print('=' * 78)
        print(os.path.relpath(r['path'], ROOT))
        if 'error' in r:
            print('  ERROR', r['error']); continue
        print('  size=%d (hdr=%d) crc32=%s' % (r['file_size'], r['copier_header'], r['crc32']))
        h = r.get('header')
        if h:
            print('  title=%-22s map=%-12s size=%-11s country=%s ver=%d' % (
                repr(h['internal_title']), h['map_mode'], h['declared_size'], h['country'], h['version']))
            print('  checksum stored=%s calc=%s ok=%s' % (
                h['checksum_stored'], h.get('checksum_calc', '?'), h.get('checksum_ok')))
        print('  free>=1K: %d bytes total | top: %s' % (
            r['free_space_total'], ', '.join('%s(%d,%s)' % (f['offset'], f['size'], f['fill']) for f in r['free_space_top'][:4])))
        print('  Shift-JIS: hira=%d kata=%d kanji=%d total=%d' % (
            r['sjis']['hiragana'], r['sjis']['katakana'], r['sjis']['kanji'], r['sjis']['total']))
        print('  SJ hot: %s' % ', '.join('%s:%d' % (b['offset'], b['count']) for b in r['sjis_hot_blocks'][:5]))
        print('  ptr2 tables=%d | top %s' % (r['ptr2_count'],
              ', '.join('%s(%d)' % (p['offset'], p['entries']) for p in r['ptr2_top'][:4])))
        print('  ptr3 tables=%d | top %s' % (r['ptr3_count'],
              ', '.join('%s(%d,%s)' % (p['offset'], p['entries'], p['order']) for p in r['ptr3_top'][:4])))
    print('\nJSON -> %s' % outpath)

if __name__ == '__main__':
    main()