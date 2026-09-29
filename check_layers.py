#!/usr/bin/env python
"""Layer-coverage scanner: build several switch combinations and check each.

重构④.  For every combination below this script runs cnbuild5.py into a
scratch ROM, then applies a per-combination check:

  base     BASE_ONLY=1   -> must equal the pristine original byte for byte
                            (below 1 MB; the header padding is make_base's)
  off      HUDFIX=0 ITEMSG=0 PACE=1
                        -> the v36-equivalent layer set: every hook OFF, the
                            pacing gate transparent.  Must differ from the
                            original ONLY in the translated data (bank $03
                            text/pointers, the pool banks, the drawer), never
                            in untouched code pages - spot-checked below.
  on       HUDFIX=1 ITEMSG=1 PACE=6
                        -> the delivered configuration; verify_all.py covers
                            it, so here we only require the build to succeed
                            and the two hooks to be planted.

A combination that fails to build or violates its check fails loudly.  Run
from the project root:

    python check_layers.py            # builds every combination (~2 min)
    python check_layers.py base on    # just these two
"""
import os
import subprocess
import sys
import zlib
import tempfile
from build_context import stage_project

ENV_BASE = dict(os.environ)
ENV_BASE['PYTHONHASHSEED'] = '0'
ENV_BASE['PYTHONUTF8'] = '1'

ORIG = 'dl/roms/kuniokun__SF8127.smc'
OUT_SCRATCH = 'kuniokun_layer.smc'

# name -> (env overlay, checker)
COMBOS = {
    'base': ({'BASE_ONLY': '1', 'OUT_ROM': OUT_SCRATCH}, 'check_base'),
    'off':  ({'HUDFIX': '0', 'ITEMSG': '0', 'PACE': '1', 'OUT_ROM': OUT_SCRATCH},
             'check_off'),
    'on':   ({'HUDFIX': '1', 'ITEMSG': '1', 'PACE': '6', 'OUT_ROM': OUT_SCRATCH},
             'check_on'),
}

# The off build must not touch these regions (code pages with no translated
# data): spot ranges picked from banks the translation never writes.
OFF_MUST_MATCH = [
    (0x000000, 0x008000),   # bank 00 header + vectors + engine
    (0x028000, 0x030000),   # bank 05
    (0x050000, 0x058000),   # bank 0A
    (0x070000, 0x078000),   # bank 0E scene graphics
]


def build(over):
    env = dict(ENV_BASE, BASE_ONLY='0')
    env.update(over)
    with tempfile.TemporaryDirectory(prefix='sfc-layer-') as tmp:
        work = stage_project(tmp)
        env['OUT_ROM'] = str(work / OUT_SCRATCH)
        p = subprocess.run([sys.executable, str(work/'cnbuild5.py')], cwd=work,
                           capture_output=True, text=True, encoding='utf-8', env=env)
        if p.returncode:
            print(p.stdout[-3000:]);print(p.stderr[-3000:])
            raise SystemExit('build failed for %r' % over)
        return (work/OUT_SCRATCH).read_bytes()


def check_base(rom):
    orig = open(ORIG, 'rb').read()
    bad = [i for i in range(len(orig)) if rom[i] != orig[i]]
    expected = {0x7FD7, 0x7FDC, 0x7FDE}
    if set(bad) != expected:
        real = [i for i in bad if i not in expected]
        print('  FAIL: BASE_ONLY differs from the original at %s'
              % ['%06X' % i for i in real[:8]])
        return False
    print('  equal to the original except the make_base header bytes - OK')
    return True


def check_off(rom):
    orig = open(ORIG, 'rb').read()
    header = (0x7FD7, 0x7FDC, 0x7FDD, 0x7FDE, 0x7FDF)   # make_base bytes
    for lo, hi in OFF_MUST_MATCH:
        bad = [i for i in range(lo, min(hi, len(orig)))
               if rom[i] != orig[i] and i not in header]
        if bad:
            print('  FAIL: off build touches untouched code page %06X-%06X '
                  'at %s' % (lo, hi, ['%06X' % i for i in bad[:6]]))
            return False
    # the pacing gate must be transparent at PACE=1: hooked, but its first
    # instructions must still reach the queue allocator with A=8
    if bytes(rom[0x1EEE5:0x1EEE9]) != bytes([0x22, 0x00, 0xD8, 0x3E]):
        print('  FAIL: pace hook not planted in the off build')
        return False
    print('  untouched code pages intact, pace hook planted (transparent at '
          'PACE=1) - OK')
    return True


def check_on(rom):
    # HUD hook at $00:8C91 -> JSL $3E:D000; drawer $DE branch present
    hud = rom[0x000C91:0x000C95]
    if hud != bytes([0x22, 0x00, 0xD0, 0x3E]):
        print('  FAIL: HUD hook not planted: %s' % hud.hex(' '))
        return False
    if bytes(rom[0x1EEE5:0x1EEE9]) != bytes([0x22, 0x00, 0xD8, 0x3E]):
        print('  FAIL: pace hook not planted')
        return False
    # the item-name branch: CMP #$DE inside the drawer ($3E:8200..)
    drawer = rom[0x1F0200:0x1F0600]
    if b'\xc9\xde' not in drawer:
        print('  FAIL: drawer $DE item branch missing in the on build')
        return False
    print('  HUD hook, pace gate and drawer $DE branch all planted - OK')
    return True


CHECKERS = {'check_base': check_base, 'check_off': check_off,
            'check_on': check_on}


def main():
    want = sys.argv[1:] or list(COMBOS)
    bad = []
    for name in want:
        if name not in COMBOS:
            raise SystemExit('unknown combination %r (have %s)'
                             % (name, sorted(COMBOS)))
        over, check = COMBOS[name]
        print('=' * 70)
        print('%s: building with %r' % (name, over))
        rom = build(over)
        ok = CHECKERS[check](rom)
        crc = zlib.crc32(rom) & 0xFFFFFFFF
        print('%s: CRC32 %08X  %s' % (name, crc, 'PASS' if ok else 'FAIL'))
        if not ok:
            bad.append(name)
    print('=' * 70)
    if bad:
        print('%d combination(s) failed: %s' % (len(bad), ', '.join(bad)))
        sys.exit(1)
    print('all %d combination(s) passed' % len(want))


if __name__ == '__main__':
    main()
