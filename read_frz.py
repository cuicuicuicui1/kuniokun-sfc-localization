"""Read a snes9x freeze file (.frz / Saves/<rom>.NNN).

The format is gzip'd and then a sequence of tagged sections:

    <TAG>:<6 hex digits of length>:<that many bytes>

Tags seen: NAM, CPU, REG, PPU, DMA, VRA (64 KB VRAM), SRA (SRAM), FIL, SND, ...

    python read_frz.py <file> [outdir]
"""
import gzip
import os
import re
import sys

TAG = re.compile(rb'([A-Z]{3}):([0-9]{6}):')   # length is DECIMAL


def sections(path):
    raw = open(path, 'rb').read()
    try:
        data = gzip.decompress(raw)
    except OSError:
        data = raw
    i = 0
    out = []
    while i < len(data) - 10:
        m = TAG.match(data, i)
        if not m:
            i += 1
            continue
        tag = m.group(1).decode()
        n = int(m.group(2), 10)
        body = data[m.end():m.end() + n]
        out.append((tag, m.start(), body))
        i = m.end() + n
    return out


def main():
    path = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else 'hw'
    secs = sections(path)
    print('%s: %d sections' % (path, len(secs)))
    for tag, off, body in secs:
        print('  %s at %8d  %8d bytes' % (tag, off, len(body)))
    vram = next((b for t, _o, b in secs if t == 'VRA'), None)
    if vram:
        name = os.path.join(outdir, os.path.basename(path) + '_vram.bin')
        open(name, 'wb').write(vram)
        print('wrote %s (%d bytes)' % (name, len(vram)))
    sra = next((b for t, _o, b in secs if t == 'SRA'), None)
    if sra:
        open(os.path.join(outdir, os.path.basename(path) + '_sram.bin'), 'wb').write(sra)
    cpu = next((b for t, _o, b in secs if t == 'CPU'), None)
    if cpu:
        print('CPU block: %s' % cpu.hex(' '))
    reg = next((b for t, _o, b in secs if t == 'REG'), None)
    if reg:
        print('REG block: %s' % reg.hex(' '))


if __name__ == '__main__':
    main()
