"""Scan the SF8127 ROM for pointer tables and text regions."""
import struct, json, sys
import kuniokun_map as M

ROM = 'dl/roms/kuniokun__SF8127.smc'
d = open(ROM, 'rb').read()
N = len(d)

# ---------------------------------------------------------------- helpers
def to_rom(v, bank):
    """LoROM bank-relative 16-bit pointer -> ROM offset."""
    return bank * 0x8000 + (v - 0x8000)

KNOWN = set(ch for ch in M.CODE.values() if not ch.startswith('{'))
def quality(text):
    """fraction of chars that are known glyphs (not {XX} placeholders)."""
    if not text:
        return 0.0
    k = sum(1 for ch in text if ch in KNOWN)
    return k / len(text)

# ---------------------------------------------------------------- u16 table scan
def scan_u16(minlen=8, maxlen=400):
    cands = []
    for base in range(0, N - 2 * minlen):
        prev = -1
        L = 0
        while L < maxlen:
            o = base + 2 * L
            if o + 2 > N:
                break
            v = d[o] | (d[o + 1] << 8)
            if v <= prev or v < 0x8000:
                break
            prev = v
            L += 1
        if L >= minlen:
            cands.append((base, L))
    return cands

def maximal(cands):
    """drop candidates fully contained (as offset ranges) in a longer one."""
    out = []
    for base, L in sorted(cands, key=lambda x: -x[1]):
        end = base + 2 * L
        contained = False
        for b2, L2 in out:
            if b2 <= base and base + 2 * L <= b2 + 2 * L2:
                contained = True
                break
        if not contained:
            out.append((base, L))
    return sorted(out)

print('scanning u16 tables ...')
raw = scan_u16()
tabs = maximal(raw)
print('raw candidates:', len(raw), 'maximal:', len(tabs))

# score each candidate for text-likeness over banks 0..31
def table_targets(base, L, bank, sample=12):
    vals = [d[base + 2 * i] | (d[base + 2 * i + 1] << 8) for i in range(min(L, sample))]
    return [to_rom(v, bank) for v in vals]

def score_table(base, L, bank):
    offs = table_targets(base, L, bank)
    qs = []
    for o in offs:
        if o < 0 or o >= N:
            return -1
        t, _ = M.decode(d, o, 24)
        qs.append(quality(t))
    return sum(qs) / len(qs)

results = []
for base, L in tabs:
    best = (-1, None)
    for bank in range(32):
        s = score_table(base, L, bank)
        if s > best[0]:
            best = (s, bank)
    results.append((base, L, best[1], best[0]))

results.sort(key=lambda x: -x[3])
print('\nTop u16 candidates (base, len, bank, quality):')
for base, L, bank, q in results[:40]:
    vals = [d[base + 2 * i] | (d[base + 2 * i + 1] << 8) for i in range(min(L, 3))]
    print('  %06X len=%3d bank=%2d q=%.3f first=%s' %
          (base, L, bank, q, ' '.join('%04X' % v for v in vals)))
