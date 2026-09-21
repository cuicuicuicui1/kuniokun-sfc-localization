"""Refined discovery: u16 and 3-byte text pointer tables."""
import struct
from collections import defaultdict

d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()
N = len(d)

def runvals(base, step, maxn=3000):
    vals = []; prev = -1
    for i in range(maxn):
        o = base + step * i
        if o + step > N: break
        if step == 2:
            v = d[o] | (d[o + 1] << 8)
        else:
            v = d[o] | (d[o + 1] << 8) | (d[o + 2] << 16)
        if v <= prev: break
        if step == 2 and v < 0x8000: break
        vals.append(v); prev = v
    return vals

def boundary_score_u16(vals, bank, sample=100):
    ok = 0; tot = 0
    for i in range(min(len(vals), sample) - 1):
        nxt = bank * 0x8000 + (vals[i + 1] - 0x8000)
        if 0 <= nxt - 2 < N and d[nxt - 2] == 0xF2: ok += 1
        tot += 1
    return ok / tot if tot else 0.0

# ---------- u16 candidates
print('=== u16 tables ===')
cands = []
for base in range(0, N - 16):
    v = runvals(base, 2, maxn=1200)
    if len(v) >= 8:
        cands.append((base, len(v)))
print('raw u16 runs:', len(cands))

scored = []
for base, L in cands:
    best = (0.0, None)
    for bank in range(32):
        s = boundary_score_u16(runvals(base, 2, maxn=100), bank)
        if s > best[0]: best = (s, bank)
    if best[0] >= 0.5:
        scored.append((base, L, best[1], best[0]))

# keep longest per overlapping group
scored.sort(key=lambda x: -x[1])
kept = []
for c in scored:
    b, L = c[0], c[1]
    if not any(b < kb + 2 * kL and kb < b + 2 * L for kb, kL in [(k[0], k[1]) for k in kept]):
        kept.append(c)

# canonical start: walk back while previous u16 still < first value
final = []
for base, L, bank, s in kept:
    vals = runvals(base, 2, maxn=L)
    first = vals[0]
    b = base
    while b - 2 >= 0:
        pv = d[b - 2] | (d[b - 1] << 8)
        if pv >= 0x8000 and pv < first:
            first = pv; b -= 2; L += 1
        else:
            break
    final.append((b, L, bank, s))

for base, L, bank, s in sorted(final, key=lambda x: x[0]):
    vals = runvals(base, 2, maxn=L)
    t0 = bank * 0x8000 + (vals[0] - 0x8000)
    tN = bank * 0x8000 + (vals[-1] - 0x8000)
    print('  tbl=%06X len=%3d bank=%2d score=%.2f targets %06X..%06X' % (base, L, bank, s, t0, tN))

# ---------- 3-byte candidates
print('\n=== 3-byte monotonic runs (>=8) ===')
c3 = []
for base in range(0, N - 30):
    vals = runvals(base, 3, maxn=1500)
    if len(vals) >= 8:
        c3.append((base, len(vals)))
print('raw 3-byte runs:', len(c3))
# score: consecutive targets should end with F2 (24-bit target -> rom offset = bank*0x8000 + (addr-0x8000))
def to_rom24(v):
    lo = v & 0xFFFF; bk = (v >> 16) & 0xFF
    if not (0x8000 <= lo <= 0xFFFF): return -1
    return bk * 0x8000 + (lo - 0x8000)
scored3 = []
for base, L in c3:
    vals = runvals(base, 3, maxn=min(L, 120))
    if any(to_rom24(v) < 0 or to_rom24(v) >= N for v in vals): continue
    ok = 0
    for i in range(len(vals) - 1):
        nx = to_rom24(vals[i + 1])
        if nx - 2 >= 0 and d[nx - 2] == 0xF2: ok += 1
    sc = ok / (len(vals) - 1)
    if sc >= 0.5: scored3.append((base, L, sc))
for base, L, sc in sorted(scored3, key=lambda x: -x[1])[:30]:
    vals = runvals(base, 3, maxn=4)
    print('  tbl=%06X len=%3d score=%.2f first=%s' % (base, L, sc, ' '.join('%06X' % v for v in vals)))
