#!/usr/bin/env python3
"""Is SRW4's main script plain SJIS, transformed, or compressed?"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = r"F:\BaiduNetdiskDownload\SFC"

# Terms that MUST appear constantly in a Super Robot Wars script
TERMS = ['ガンダム', 'マジンガー', 'ゲッター', 'ロボット', '戦闘', '出撃', '改造',
         'の', 'です', 'ます', 'ダメージ', '武器', '修理', '補給', '移動']
TRANSFORMS = {
    'plain  ': lambda b: b,
    'swap16 ': lambda b: b''.join(b[i+1:i+2] + b[i:i+1] for i in range(0, len(b) - 1, 2)),
    'xor8000': lambda b: b''.join(bytes([b[i], b[i+1]]) for i in range(0, len(b) - 1, 2)),
}

def main():
    rows = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if f.lower().endswith(('.sfc', '.smc')) and 'srw4' in f.lower():
                rows.append(os.path.join(dp, f))
    rows.sort()
    for t in rows:
        raw = open(t, 'rb').read()
        body = raw[512 if len(raw) % 32768 == 512 else 0:]
        print('=' * 84)
        print('%s (%d B)' % (os.path.basename(t), len(body)))
        # plain SJIS hit counts
        out = []
        for term in TERMS:
            s = term.encode('shift_jis')
            c = 0; st = 0; first = -1
            while True:
                k = body.find(s, st)
                if k < 0: break
                if first < 0: first = k
                c += 1; st = k + 1
            out.append('%s=%d%s' % (term, c, ('@0x%X' % first) if first >= 0 else ''))
        print('  plain SJIS:  ' + '  '.join(out[:8]))
        print('               ' + '  '.join(out[8:]))
        # swapped-byte-pair search for the strongest terms
        sw = []
        for term in TERMS[:6]:
            s = term.encode('shift_jis')
            t2 = b''.join(s[i+1:i+2] + s[i:i+1] for i in range(0, len(s) - 1, 2))
            sw.append('%s=%d' % (term, body.count(t2)))
        print('  byte-swapped:', '  '.join(sw))

if __name__ == '__main__':
    main()