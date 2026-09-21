# -*- coding: utf-8 -*-
"""WRAM scratch addresses are $0D40+; '%02X' would print three hex digits.
Mask every address operand in the emitted 65816 code to its low byte (the high
byte is the literal 0D in those format strings)."""
import re

src = open('cnbuild5.py', encoding='utf-8').read()
lines = src.split('\n')
pat = re.compile(r"^(\s*a\.hexs\('(?:[^']*)%02X 0D(?:[^']*)'\s*%\s*)(.*?)(\)\s*(?:#.*)?)$")
out = []
i = 0
n = 0
while i < len(lines):
    ln = lines[i]
    if '%02X 0D' in ln and "' %" not in ln and i + 1 < len(lines):
        ln = ln + lines[i + 1]
        i += 1
    m = pat.match(ln)
    if m:
        pre, args, post = m.group(1), m.group(2), m.group(3)
        fmt = pre[pre.index("'"):pre.rindex("'") + 1]
        fmt2 = fmt.replace('%02X 0D', '%s')
        body = args.strip()
        if body.startswith('(') and body.endswith(')'):
            parts = [p.strip() for p in body[1:-1].split(',')]
        else:
            parts = [body]
        cnt = fmt.count('%02X 0D')
        assert len(parts) == cnt, (ln, parts, cnt)
        masked = '(%s)' % ', '.join('(%s) & 0xFF' % p for p in parts)
        new = pre[:pre.index("'")] + fmt2 + ' % ' + masked + post
        n += 1
        out.append(new)
    else:
        out.append(ln)
    i += 1
open('cnbuild5.py', 'w', encoding='utf-8').write('\n'.join(out))
print('rewrote %d address format strings' % n)
