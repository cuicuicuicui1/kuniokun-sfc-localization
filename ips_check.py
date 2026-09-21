#!/usr/bin/env python3
"""Analyze IPS patch files and test whether the provided ROMs already contain them."""
import os, struct, sys, zlib

ROOT = r"F:\BaiduNetdiskDownload\SFC"

def parse_ips(path):
    d = open(path, 'rb').read()
    if d[:5] != b'PATCH': raise ValueError('not IPS: %r' % d[:8])
    i = 5; recs = []
    while i < len(d):
        if d[i:i+3] == b'EOF': break
        off = (d[i] << 16) | (d[i+1] << 8) | d[i+2]; i += 3
        sz = (d[i] << 8) | d[i+1]; i += 2
        if sz == 0:
            rl = (d[i] << 8) | d[i+1]; i += 2
            val = d[i]; i += 1
            recs.append((off, rl, bytes([val]) * rl, 'RLE'))
        else:
            recs.append((off, sz, d[i:i+sz], 'RAW')); i += sz
    return recs

def find_roms():
    out = {}
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')):
                p = os.path.join(dp, f)
                raw = open(p, 'rb').read()
                ch = 512 if len(raw) % 32768 == 512 else 0
                out[(len(raw), zlib.crc32(raw[ch:]) & 0xFFFFFFFF)] = p
    return out

def main():
    roms = find_roms()
    print('ROMs:')
    for (sz, crc), p in sorted(roms.items()):
        print('  %08X  %8d  %s' % (crc, sz, os.path.relpath(p, ROOT)))
    print()
    ipss = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith('.ips'): ipss.append(os.path.join(dp, f))
    for p in sorted(ipss):
        try:
            recs = parse_ips(p)
        except Exception as e:
            print('%-70s  %s' % (os.path.relpath(p, ROOT), e)); continue
        tot = sum(r[1] for r in recs)
        mx = max(r[0] + r[1] for r in recs)
        mn = min(r[0] for r in recs)
        print('%-62s recs=%-6d bytes=%-9d span=0x%06X..0x%06X' % (
            os.path.relpath(p, ROOT), len(recs), tot, mn, mx))
        # try matching against each ROM
        results = []
        for (sz, crc), rp in sorted(roms.items()):
            raw = open(rp, 'rb').read()
            ch = 512 if len(raw) % 32768 == 512 else 0
            body = raw[ch:]
            if mx > len(body):
                continue
            same = 0; diff = 0
            for off, ln, data, kind in recs:
                if off + ln > len(body): break
                if body[off:off+len(data)] == data: same += 1
                else: diff += 1
            tot2 = same + diff
            results.append((same / max(tot2, 1), same, tot2, os.path.relpath(rp, ROOT)))
        results.sort(reverse=True)
        for ratio, same, tot2, name in results[:3]:
            print('      best vs %-56s -> %5.1f%% (%d/%d)' % (name[-56:], 100*ratio, same, tot2))
        print()

if __name__ == '__main__':
    main()