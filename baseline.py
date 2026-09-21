#!/usr/bin/env python3
"""Baseline test: is the detected 'SJIS text' real signal or random coincidence?"""
import os, sys, random, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recon2 import text_runs, sj_class

ROOT = r"F:\BaiduNetdiskDownload\SFC"

def analyze(data, label):
    runs = text_runs(data, minchars=8)
    jp = [r for r in runs if r['jp_chars'] >= 3]
    cov = sum(r['end'] - r['start'] for r in jp)
    return len(jp), cov, (cov / len(data) * 100 if data else 0)

def main():
    targets = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')): targets.append(os.path.join(dp, f))
    targets.sort()
    seen = {}
    print('%-42s %6s %8s %8s %8s %8s' % ('file', 'idx', 'real_jp', 'real_cov', 'rand_avg', 'ratio'))
    for t in targets:
        raw = open(t, 'rb').read()
        ch = 512 if len(raw) % 32768 == 512 else 0
        body = raw[ch:]
        crc = zlib.crc32(body) & 0xFFFFFFFF
        if crc in seen: 
            print('%-42s == duplicate of %s' % (os.path.basename(t)[:42], seen[crc]))
            continue
        seen[crc] = os.path.basename(t)[:42]
        nj, cov, pct = analyze(body, t)
        # random baseline: same length, random byte distribution (shuffled real bytes preserves histogram)
        rr = random.Random(1234)
        base = []
        for trial in range(3):
            b = bytearray(body)
            shuf = bytearray(body)
            rr.shuffle(shuf)
            _, c2, _ = analyze(bytes(shuf), t)
            base.append(c2)
        avg = sum(base) / len(base)
        print('%-42s %6d %8d %8d %8d %7.2fx' % (os.path.basename(t)[:42], nj, cov, int(avg),
              int(avg), cov / avg if avg else 0))
    print()
    print('legend: real_jp = #jp runs>=8; real_cov = bytes in jp runs;')
    print('        rand_avg = same count on byte-shuffled ROM (noise floor)')

if __name__ == '__main__':
    main()