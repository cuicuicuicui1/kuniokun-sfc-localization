#!/usr/bin/env python3
"""Dump hex+ASCII windows so we can see how each game really stores its text."""
import os, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = r"F:\BaiduNetdiskDownload\SFC"

def find(frag):
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')) and frag.lower() in f.lower():
                return os.path.join(dp, f)
    return None

def dump(path, off, before=0x40, after=0x180, label=''):
    raw = open(path, 'rb').read()
    ch = 512 if len(raw) % 32768 == 512 else 0
    body = raw[ch:]
    s = max(0, off - before); e = min(len(body), off + after)
    print('--- %s @0x%06X (file %s) ---' % (label, off, os.path.basename(path)))
    for o in range(s, e, 16):
        chunk = body[o:o + 16]
        asc = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        try: sj = chunk.decode('shift_jis', errors='replace').replace('\ufffd', '?')
        except Exception: sj = ''
        mark = '<' if o <= off < o + 16 else ' '
        print('%s%06X  %-47s  %-16s  %s' % (mark, o, chunk.hex(' '), asc, sj[:14]))
    print()

def main():
    # 1. SRW4 DC: where did the prose detector find dialogue?
    p = find('SRW4_DC')
    if p:
        raw = open(p, 'rb').read()
        ch = 512 if len(raw) % 32768 == 512 else 0
        body = raw[ch:]
        idx = body.find('ジェリド「そうか'.encode('shift_jis'))
        print('SRW4_DC  "ジェリド「そうか" found at 0x%06X' % idx if idx >= 0 else 'not found')
        if idx >= 0: dump(p, idx)
        idx2 = body.find('沙羅「救援'.encode('shift_jis'))
        if idx2 >= 0: dump(p, idx2, label='SRW4_DC')
    # 2. 春风DX
    p = find('TitaharuDX')
    if p:
        raw = open(p, 'rb').read(); body = raw[512 if len(raw) % 32768 == 512 else 0:]
        idx = body.find('リョクレイ「やはり'.encode('shift_jis'))
        if idx >= 0:
            print('春风DX "リョクレイ「やはり" at 0x%06X' % idx)
            dump(p, idx, label='春风DX')
    # 3. Hero Senki: the increment tables
    p = find('Hero Senki')
    if p:
        dump(p, 0x138500, before=0x20, after=0x80, label='HeroSenki JIS-order table')
        dump(p, 0x00E760, before=0x20, after=0xC0, label='HeroSenki ptr cand')
        dump(p, 0x128000, before=0x20, after=0x80, label='HeroSenki ptr cand')
    # 4. 初代热血硬派
    p = find('SF8127')
    if p: dump(p, 0x01E4CE, before=0x20, after=0xC0, label='SF8127 ptr cand')
    # 5. Doraemon 4 (has a font at 0x15C00)
    p = find('Doraemon 4')
    if p:
        dump(p, 0x15C00, before=0x10, after=0x60, label='Doraemon4 font page')
        dump(p, 0x0058D6, before=0x20, after=0xA0, label='Doraemon4 ptr cand')

if __name__ == '__main__':
    main()