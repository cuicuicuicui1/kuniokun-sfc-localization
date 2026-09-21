#!/usr/bin/env python3
"""Proper text detector: real Japanese prose is hiragana-rich and non-repetitive.
Distinguish genuine script from structural tables (repeated fills, JIS-ordered indices)."""
import os, sys, zlib
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon2 import sj_len, sj_trail, sj_class

ROOT = r"F:\BaiduNetdiskDownload\SFC"

def prose_runs(data, minchars=6, min_hira=0.35):
    """Find runs of valid SJIS that look like prose: hiragana-rich, not repetitive."""
    out = []
    n = len(data); i = 0
    while i < n - 1:
        j = i; chunks = []
        while j < n - 1:
            L = sj_len(data[j])
            if L == 1:
                chunks.append((j, 1, 'ascii')); j += 1
            elif L == 2 and sj_trail(data[j + 1]):
                chunks.append((j, 2, sj_class(data[j], data[j + 1]))); j += 2
            else:
                break
        if len(chunks) >= minchars:
            kinds = Counter(c[2] for c in chunks)
            nh = kinds['hira']; nk = kinds['kanji'] + kinds['kata']
            # repetition check: longest run of one identical 2-byte char
            maxrep = 1; cur = 1
            for a in range(1, len(chunks)):
                if chunks[a][1] == 2 and chunks[a-1][1] == 2 and \
                   data[chunks[a][0]:chunks[a][0]+2] == data[chunks[a-1][0]:chunks[a-1][0]+2]:
                    cur += 1; maxrep = max(maxrep, cur)
                else:
                    cur = 1
            frac_h = nh / len(chunks)
            # genuine prose: hiragana-dominant and not a repeated fill
            if frac_h >= min_hira and maxrep <= 3 and nk >= 1:
                out.append({'start': i, 'end': j, 'nchars': len(chunks),
                            'hira': nh, 'kanji': nk, 'maxrep': maxrep,
                            'frac_h': round(frac_h, 2)})
            i = j
        else:
            i += 1 if j == i else (j - i)
    return out

def main():
    targets = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')): targets.append(os.path.join(dp, f))
    targets.sort()
    seen = set()
    print('%-44s %7s %8s %8s %s' % ('file', '#prose', 'bytes', 'maxlen', 'sample'))
    for t in targets:
        raw = open(t, 'rb').read()
        ch = 512 if len(raw) % 32768 == 512 else 0
        body = raw[ch:]
        crc = zlib.crc32(body) & 0xFFFFFFFF
        if crc in seen: continue
        seen.add(crc)
        rs = prose_runs(body)
        rs.sort(key=lambda r: -r['nchars'])
        tot = sum(r['end'] - r['start'] for r in rs)
        smp = ''
        for r in rs[:3]:
            try: smp += '| ' + body[r['start']:r['end']].decode('shift_jis', errors='replace')[:34]
            except Exception: pass
        print('%-44s %7d %8d %8d %s' % (os.path.basename(t)[:44], len(rs), tot,
              rs[0]['nchars'] if rs else 0, smp[:80]))

if __name__ == '__main__':
    main()