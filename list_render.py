"""Render a whole list screen: consecutive entries of one table, one per row,
driven through the real patched drawer so the shared-slot colouring is exercised."""
import json, sys
from PIL import Image
import sim65816, cnbuild5 as cb, kuniokun_map as km
import render_msg as rm

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
rom = rm.rom
addr = json.load(open(BASE + '/cn_addr_map.json', encoding='utf-8'))
recs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))
PROPS = 0x01DBC5


def entry_bytes(key, limit=200):
    a = addr[key]
    out = bytearray()
    while len(out) < limit and not (rom[a] == 0xF2 and rom[a + 1] in (0xF3, 0xF4)):
        out.append(rom[a]); a += 1
    return bytes(out)


def draw_rows(keys, path, cols=14, rows=None, start_row=0):
    rows = rows or len(keys)
    cells = {}
    for ridx, key in enumerate(keys):
        msg = entry_bytes(key)
        row, col, i = start_row + ridx, 0, 0
        while i < len(msg):
            code = msg[i]
            if code >= 0xF0:            # skip control codes except nothing else
                cpu = sim65816.CPU(rom)
                cpu.pbr, cpu.pc = 0x03, 0xFC9E
                cpu.m8 = cpu.x8 = True
                cpu.db = 0x03
                cpu.bus.wram[0x12] = code
                n = 0
                while cpu.pc not in rm.CTRL_SITES and n < 300:
                    cpu.step(); n += 1
                row, col = cpu.bus.wram[0x036E], cpu.bus.wram[0x036F]
                i += 1
                continue
            cpu = sim65816.CPU(rom)
            cpu.pbr = cb.E3_DRAWER // 0x8000
            cpu.pc = 0x8000 + (cb.E3_DRAWER % 0x8000)
            cpu.m8 = cpu.x8 = True
            cpu.db = 0x03
            w = cpu.bus.wram
            w[0x03EA:0x03EA + len(msg)] = msg
            w[0x03E8], w[0x03E9] = len(msg), i
            w[0x036E], w[0x036F], w[0x09DF] = row, col, 0
            w[0x12], cpu.a = code, code
            n = 0
            while cpu.pc not in rm.RTS and n < 5000:
                cpu.step(); n += 1
            w = cpu.bus.wram
            got = bytes(w[0x0B00:0x0B00 + 8])
            if got[2:4] == bytes([0x81, 0x04]):
                caddr = got[0] | (got[1] << 8)
                hi, lo = caddr >> 8, caddr & 0xFF
                cro, cco = (hi - 0x7C) * 4 + (lo - 3) // 0x40, (lo - 3) % 0x40
                if cb.PREFIX0 <= code < cb.PREFIX0 + cb.PAGES:
                    base = 0x6000 + got[4] * 8
                    raw = b''.join(bytes([cpu.vram[base + k] & 0xFF, cpu.vram[base + k] >> 8])
                                   for k in range(16))
                    px = rm.tile_px(raw, 0) + rm.tile_px(raw, 16)
                else:
                    px = (rm.tile_px(rom, rm.FONT + km.FB[code] * 16)
                          + rm.tile_px(rom, rm.FONT + km.FA[code] * 16))
                cells[(cro, cco)] = px
            row, col = w[0x036E], w[0x036F]
            i += 2 if (cb.PREFIX0 <= code < cb.PREFIX0 + cb.PAGES) else 1
    S = 6
    img = Image.new('RGB', (cols * 8 * S, rows * 16 * S), (0, 0, 0))
    ink = ((255, 246, 230), (230, 222, 205), (205, 197, 180), (255, 255, 255))
    pix = img.load()
    for (r, c), g in cells.items():
        for y in range(16):
            for x in range(8):
                v = g[y][x]
                if not v:
                    continue
                for dy in range(S):
                    for dy2 in range(S):
                        X, Y = (c * 8 + x) * S + dy2, (r * 16 + y) * S + dy
                        if 0 <= X < img.width and 0 <= Y < img.height:
                            pix[X, Y] = ink[v]
    img.save(path)
    return len(cells)


if __name__ == '__main__':
    order = []
    for r in recs:
        if r['table_rom_off'] == PROPS:
            order.append('%06X' % r['text_rom_off'])
    print('props entries:', len(order))
    first = sys.argv[1] if len(sys.argv) > 1 else '0'
    start = int(first)
    keys = order[start:start + 10]
    print(keys)
    n = draw_rows(keys, BASE + '/list_%d.png' % start)
    print(n, 'cells')