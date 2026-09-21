"""mkvariants.py - build bisect variants of the patched ROM to localise the freeze.

E3_DRAWER = 0x1F0200 ($3E:8200), drawer copy head:
  8200 C9 C5      CMP #$C5
  8202 90 07      BCC orig      (<$C5 -> original path)
  8204 C9 D1      CMP #$D1
  8206 90 54      BCC cn        ($C5-$D0 -> my Chinese path)
  8208 4C 0B 82   JMP orig      (>= $D1 -> original path)

V1  : 0x1F0206 BCC->NOP   => every code takes the original path (no cn branch, no glyph DMA).
V1b : no DMA trigger      => cn branch runs and writes the script, but the glyph DMA never fires.
V1c : DMA trigger kept, source bank forced to $00 (wrong bank) => isolates "DMA runs" from "correct data".
"""
BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
src = open(BASE + '/kuniokun_cn.smc', 'rb').read()
print('src %d bytes, crc-file' % len(src))

D = 0x1F0200
print('drawer head:', src[D:D + 12].hex(' '))
assert src[D:D + 2] == bytes([0xC9, 0xC5]), 'unexpected drawer head'
assert src[D + 4:D + 6] == bytes([0xC9, 0xD1]), 'unexpected drawer head 2'


def make(name, patches, expect):
    rom = bytearray(src)
    for off, old, new in patches:
        assert rom[off:off + len(old)] == old, '%s: expected %s at %06X, got %s' % (
            name, old.hex(' '), off, rom[off:off + len(old)].hex(' '))
        rom[off:off + len(new)] = new
    assert len(rom) == 0x200000
    path = BASE + '/v_' + name + '.smc'
    open(path, 'wb').write(bytes(rom))
    print('wrote %s  (%s)' % (path, expect))
    return path


# V1: force the original path for everything
make('v1_nocn', [(0x1F0206, bytes([0x90, 0x54]), bytes([0xEA, 0xEA]))],
     'all codes drawn by the original drawer code (Chinese codes -> box tiles)')

# V1b: cn branch active, glyph DMA trigger NOPed
n = src.find(bytes([0xA9, 0x02, 0x8D, 0x0B, 0x42]), D)
print('DMA trigger site at 0x%06X' % n)
assert 0 <= n < D + 0x120, 'DMA trigger not inside the drawer copy'
make('v1b_nodma', [(n + 2, bytes([0x8D, 0x0B, 0x42]), bytes([0xEA, 0xEA, 0xEA]))],
     'cn branch + script writes, but no glyph DMA (tiles point at untouched font area)')

# V1c: DMA fires but reads a harmless bank ($00 instead of $21+page)
m = src.find(bytes([0x8D, 0x14, 0x43]), D)
print('DMA source bank site at 0x%06X' % m)
assert 0 <= m < D + 0x120
make('v1c_badbank', [(m + 2, bytes([0x43]), bytes([0x43]))],
     'same as v2 but with the source bank forced to $00 (garbage glyph data)')