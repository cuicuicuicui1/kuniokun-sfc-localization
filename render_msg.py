"""Render a message the way the patched game will draw it: drive the real
drawer from the patched ROM byte by byte, then paint the cells it produces."""
import json, sys
from PIL import Image
import mos65xx
import sim65816, cnbuild5 as cb, kuniokun_map as km

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
rom = open(cb.OUT_ROM, 'rb').read()
recs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))
addr = json.load(open(BASE + '/cn_addr_map.json', encoding='utf-8'))
FONT = 0x0F8000
RTS = (0x825B, 0x8304)
CTRL_SITES = tuple(i.address for i in mos65xx.disassemble(
    rom[0x01FC9E:0x01FD90], address=0x8000 + (0x01FC9E % 0x8000))
    if i.mnemonic == 'rts')

def tile_px(data, off):
    g = []
    for y in range(8):
        p0, p1 = data[off + y * 2], data[off + y * 2 + 1]
        g.append([((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1) for x in range(8)])
    return g

def render(key, path, cols=22, rows=5):
    a = addr[key]
    # a message is a chain of F2-separated segments (the loader copies one
    # segment per call); walk the whole message up to its end/page break
    msg = bytearray(); j = a
    while len(msg) < 400:
        if rom[j] == 0xF2 and j + 1 < len(rom) and rom[j + 1] in (0xF3, 0xF4):
            break
        msg.append(rom[j]); j += 1
    cells = {}                      # (row, col) -> list of 16 rows of 8 px values
    row = col = 0
    i = 0
    while i < len(msg):
        code = msg[i]
        cpu = sim65816.CPU(rom)
        cpu.pbr = cb.E3_DRAWER // 0x8000
        cpu.pc = 0x8000 + (cb.E3_DRAWER % 0x8000)
        cpu.m8 = cpu.x8 = True
        cpu.db = 0x03
        w = cpu.bus.wram
        w[0x03EA:0x03EA + len(msg)] = msg
        w[0x03E8], w[0x03E9] = len(msg), i
        w[0x036E], w[0x036F], w[0x09DF] = row, col, 0
        w[0x12] = code
        cpu.a = code
        if code >= 0xF0:
            # control code: the consumer calls the handler at $03:FC9E instead of
            # the drawer, so run it here to get authentic row/column behaviour
            cpu.pbr = 0x03
            cpu.pc = 0xFC9E
            cpu.a = code
            n = 0
            while cpu.pc not in CTRL_SITES and n < 300:
                cpu.step(); n += 1
            row, col = cpu.bus.wram[0x036E], cpu.bus.wram[0x036F]
            i += 1
            continue
        n = 0
        while cpu.pc not in RTS and n < 5000:
            cpu.step(); n += 1
        w = cpu.bus.wram
        got = bytes(w[0x0B00:0x0B00 + 8])
        if len(got) == 8 and got[:4] == bytes([w[0x0B00], w[0x0B00 + 1], 0x81, 0x04]):
            caddr = got[0] | (got[1] << 8)
            _hi, _lo = caddr >> 8, caddr & 0xFF
            cro, cco = (_hi - 0x7C) * 4 + (_lo - 3) // 0x40, (_lo - 3) % 0x40
            if is_cn := (cb.PREFIX0 <= code < cb.PREFIX0 + cb.PAGES):
                pair = got[4]
                base = 0x6000 + pair * 8
                raw = b''.join(bytes([cpu.vram[base + k] & 0xFF, cpu.vram[base + k] >> 8])
                               for k in range(16))
                px = tile_px(raw, 0) + tile_px(raw, 16)
            else:
                px = tile_px(rom, FONT + km.FB[code] * 16) + tile_px(rom, FONT + km.FA[code] * 16)
            cells[(cro, cco)] = px
        row, col = w[0x036E], w[0x036F]
        i += 2 if (cb.PREFIX0 <= code < cb.PREFIX0 + cb.PAGES) else 1
    S = 6
    img = Image.new('RGB', (cols * 8 * S, rows * 16 * S), (0, 0, 0))
    ink = ((255, 246, 230), (230, 222, 205), (205, 197, 180), (255, 255, 255))
    px = img.load()
    for (r, c), g in cells.items():
        for y in range(16):
            for x in range(8):
                v = g[y][x]
                if v == 3:
                    v = 3                       # colour 3 shows as white
                col_ = ink[v] if v else None
                if col_ is None:
                    continue
                for dy in range(S):
                    for dx in range(S):
                        X, Y = (c * 8 + x) * S + dx, (r * 16 + y) * S + dy
                        if 0 <= X < img.width and 0 <= Y < img.height:
                            px[X, Y] = col_
    img.save(path)
    return len(cells)

if __name__ == '__main__':
    picks = [('019921', 'box_a'), ('019C34', 'box_b'), ('01DCA1', 'box_list'),
             ('01E239', 'box_place')]
    for key, tag in picks:
        n = render(key, BASE + '/msg_%s.png' % tag)
        print(key, tag, n, 'cells')
