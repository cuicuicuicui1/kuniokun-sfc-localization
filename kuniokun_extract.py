"""Extract all text from SF8127 and write kuniokun_text.json/.txt/_stats.txt."""
import struct, json, re
from collections import Counter, defaultdict
import kuniokun_map as M

ROM = 'dl/roms/kuniokun__SF8127.smc'
d = open(ROM, 'rb').read()
N = len(d)
BANK = 3

# (table_rom_off, n_entries, label)  -- all bank $03
TABLES = [
    (0x193B5, 694, 'script/status (large)'),
    (0x1DBC5, 110, 'items/shop'),
    (0x1E098,  35, 'menus A'),
    (0x1E1D5,  50, 'menus B'),
    (0x1E4CE, 124, 'menus C'),
]

def conv(v):
    return BANK * 0x8000 + (v - 0x8000)

def read_ptrs(base, n):
    return [struct.unpack('<H', d[base + 2 * i:base + 2 * i + 2])[0] for i in range(n)]

def decode_until_term(off, limit):
    """Decode starting at off until a F2 xx control byte (inclusive), bounded by limit."""
    out = []
    i = off
    while i < limit and i < N:
        c = d[i]
        if c == 0xF2 and i + 1 < N:
            out.append('{F2%02X}' % d[i + 1])
            i += 2
            break
        out.append(M.CODE[c])
        i += 1
    return ''.join(out), i

records = []
regions = []

for tbl_off, n, label in TABLES:
    ptrs = read_ptrs(tbl_off, n)
    assert all(0x8000 <= p <= 0xFFFF for p in ptrs)
    tgt = [conv(p) for p in ptrs]
    # next data boundary: next table start, or scan forward
    if tbl_off == 0x193B5:
        limit_all = 0x1DBC5
    elif tbl_off == 0x1DBC5:
        limit_all = 0x1E098
    elif tbl_off == 0x1E098:
        limit_all = 0x1E1D5
    elif tbl_off == 0x1E1D5:
        limit_all = 0x1E4CE
    else:
        limit_all = 0x1EA00

    region_recs = []
    for i in range(n):
        start = tgt[i]
        if i + 1 < n:
            # the full slice between consecutive pointers IS one string,
            # and it may contain internal line-break controls.
            end = tgt[i + 1]
            text = M.decode(d, start, end - start)[0]
            nbytes = end - start
        else:
            # last entry: decode until its terminating F2xx control
            text, real_end = decode_until_term(start, limit_all)
            nbytes = real_end - start
        rec = {
            'table_rom_off': tbl_off, 'index': i, 'ptr_value': ptrs[i],
            'text_rom_off': start, 'text': text, 'nbytes': nbytes,
        }
        records.append(rec)
        region_recs.append(rec)

    region_start = tgt[0]
    region_end = region_recs[-1]['text_rom_off'] + region_recs[-1]['nbytes']
    regions.append({
        'table_rom_off': tbl_off, 'label': label, 'n': n,
        'region_start': region_start, 'region_end': region_end,
        'bytes': region_end - region_start,
        'recs': region_recs,
    })

# ------------------------------------------------------------------ outputs
with open('kuniokun_text.json', 'w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=1)

with open('kuniokun_text.txt', 'w', encoding='utf-8') as f:
    for r in regions:
        f.write('=' * 78 + '\n')
        f.write('REGION table=0x%06X  %s  entries=%d  rom 0x%06X..0x%06X (%d bytes)\n' %
                (r['table_rom_off'], r['label'], r['n'], r['region_start'],
                 r['region_end'], r['bytes']))
        f.write('=' * 78 + '\n')
        for rec in r['recs']:
            f.write('0x%06X [%3d] %s\n' % (rec['text_rom_off'], rec['index'], rec['text']))
        f.write('\n')

# ------------------------------------------------------------------ analysis
ctrl = Counter()
ctrl_by_region = defaultdict(Counter)
unknown = Counter()
for r in regions:
    for rec in r['recs']:
        for m in re.finditer(r'\{(F2[0-9A-F]{2}|[0-9A-F]{2})\}', rec['text']):
            g = m.group(1)
            if g.startswith('F2') and len(g) == 4:
                ctrl[g] += 1
                ctrl_by_region[r['label']][g] += 1
            else:
                unknown[g] += 1

total_strings = len(records)
total_bytes = sum(r['bytes'] for r in regions)
total_chars = sum(len(rec['text']) for rec in records)

# heuristic classification
def classify(t):
    if ':' in t:
        return 'dialogue (speaker ":")'
    if len(t) >= 40:
        return 'long text'
    if len(t) <= 20:
        return 'short/menu/name'
    return 'medium'

classes = Counter()
class_by_region = defaultdict(Counter)
for r in regions:
    for rec in r['recs']:
        c = classify(rec['text'])
        classes[c] += 1
        class_by_region[r['label']][c] += 1

with open('kuniokun_text_stats.txt', 'w', encoding='utf-8') as f:
    f.write('SF8127 text extraction stats\n')
    f.write('total strings: %d\n' % total_strings)
    f.write('total text bytes: %d\n' % total_bytes)
    f.write('total decoded characters: %d\n\n' % total_chars)
    f.write('REGIONS\n')
    for r in regions:
        f.write('-' * 70 + '\n')
        f.write('table_rom_off 0x%06X   %s\n' % (r['table_rom_off'], r['label']))
        f.write('region ROM     0x%06X..0x%06X  (%d bytes)\n' %
                (r['region_start'], r['region_end'], r['bytes']))
        f.write('strings %d\n' % r['n'])
        samp = r['recs'][:3]
        for s in samp:
            f.write('  sample 0x%06X: %s\n' % (s['text_rom_off'], s['text'][:70]))
    f.write('\nCLASSIFICATION (heuristic)\n')
    for k, v in classes.most_common():
        f.write('  %-24s %d\n' % (k, v))
    f.write('\nper region:\n')
    for r in regions:
        f.write('  0x%06X %-22s %s\n' % (r['table_rom_off'], r['label'],
                                         dict(class_by_region[r['label']])))
    f.write('\nCONTROL BYTES F2xx (occurrences)\n')
    for k, v in ctrl.most_common():
        f.write('  %s %d\n' % (k, v))
    f.write('\n  per region:\n')
    for r in regions:
        f.write('    0x%06X %-22s %s\n' % (r['table_rom_off'], r['label'],
                                           dict(ctrl_by_region[r['label']])))
    f.write('\nUNKNOWN TILE PLACEHOLDERS {XX} (tile number: count)\n')
    for k, v in unknown.most_common():
        f.write('  %s %d\n' % (k, v))

print('strings', total_strings, 'bytes', total_bytes, 'chars', total_chars)
print('controls:', dict(ctrl))
print('unknown tiles:', len(unknown), 'distinct;', dict(unknown.most_common(20)))
print('classes:', dict(classes))
