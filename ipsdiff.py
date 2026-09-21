"""Count where kuniokun_cn.smc differs from the original ROM.

Usage: python -u ipsdiff.py
"""
import sys

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
ORIG = BASE + '/dl/roms/kuniokun__SF8127.smc'
NEW = BASE + '/kuniokun_cn.smc'

a = open(ORIG, 'rb').read()
b = open(NEW, 'rb').read()
print('orig %d, new %d' % (len(a), len(b)))

runs = []
n = max(len(a), len(b))
i = 0
while i < n:
    x = a[i] if i < len(a) else None
    y = b[i] if i < len(b) else None
    if x != y:
        j = i
        while j < n:
            x = a[j] if j < len(a) else None
            y = b[j] if j < len(b) else None
            if x == y:
                break
            j += 1
        runs.append((i, j - i))
        i = j
    else:
        i += 1

print('runs: %d' % len(runs))
tot = sum(l for _, l in runs)
print('changed bytes: %d' % tot)

# histogram by log2 size
import collections
h = collections.Counter()
for _, l in runs:
    h[min(20, l.bit_length())] += 1
for k in sorted(h):
    print('  run length ~2^%-2d (<=%7d): %5d runs' % (k, 1 << k, h[k]))

# group by 32 KB bank
banks = collections.Counter()
for off, l in runs:
    banks[off >> 15] += 1
print('runs per 32KB bank:')
for k in sorted(banks):
    print('  bank %02X (rom 0x%06X..0x%06X): %5d runs' % (k, k << 15, ((k + 1) << 15) - 1, banks[k]))

# biggest runs
runs.sort(key=lambda r: -r[1])
print('largest runs:')
for off, l in runs[:15]:
    print('  0x%06X  %d bytes' % (off, l))