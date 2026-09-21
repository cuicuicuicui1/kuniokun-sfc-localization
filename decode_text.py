#!/usr/bin/env python3
"""Decode the actual Japanese text found in each ROM, and characterise its encoding."""
import os, sys, zlib
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon2 import text_runs, sj_len, sj_class

ROOT = r"F:\BaiduNetdiskDownload\SFC"

def decode(b):
    try: return b.decode('shift_jis', errors='replace')
    except Exception: return repr(b)

def main():
    targets = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')): targets.append(os.path.join(dp, f))
    targets.sort()
    seen = set()
    for t in targets:
        raw = open(t, 'rb').read()
        ch = 512 if len(raw) % 32768 == 512 else 0
        body = raw[ch:]
        crc = zlib.crc32(body) & 0xFFFFFFFF
        if crc in seen: continue
        seen.add(crc)
        runs = [r for r in text_runs(body, minchars=8) if r['jp_chars'] >= 3]
        runs.sort(key=lambda r: -(r['end'] - r['start']))
        print('=' * 100)
        print('%s   (%d B)' % (os.path.basename(t), len(body)))
        # control-code census: which bytes appear immediately before a run start
        before = Counter(); after = Counter()
        for r in runs:
            s, e = r['start'], r['end']
            if s > 0: before[body[s - 1]] += 1
            if e < len(body): after[body[e]] += 1
        print('  bytes preceding runs :', ' '.join('%02X:%d' % kv for kv in before.most_common(8)))
        print('  bytes following runs :', ' '.join('%02X:%d' % kv for kv in after.most_common(8)))
        for r in runs[:6]:
            s, e = r['start'], r['end']
            ctx = body[max(0, s - 4):min(len(body), e + 4)]
            pre = body[max(0, s - 4):s].hex(' ')
            post = body[e:min(len(body), e + 4)].hex(' ')
            print('  @0x%06X len=%4d [%s] %s [%s]' % (s, e - s, pre, decode(body[s:e])[:110], post))
        # per-char kind census
        k = Counter()
        for r in runs: k.update(r['kinds'])
        print('  char kinds:', dict(k))

if __name__ == '__main__':
    main()