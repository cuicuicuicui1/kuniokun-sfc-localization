-- menu13: end to end test of the new row wipe.  Poke the box map with the
-- window tiles, arm the pending wipe by hand ($0BFB = base | $80), advance the
-- dialogue so a drawing sequence ends (step $03:F700) and check that the four
-- rows the base points at come back blank.
-- env: HW_TAG HW_ROM
local TAG  = os.getenv('HW_TAG') or 'menu13'
local ROMF = os.getenv('HW_ROM') or 'kuniokun_cn.smc'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)

local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function poke(x, v) memory.write_u8(x * 2, v % 256, 'VRAM')
                          memory.write_u8(x * 2 + 1, math.floor(v / 256), 'VRAM') end
local function rowcells(r)
  local t = {}
  for c = 0, 31 do
    local v = vw(0x7C00 + r * 0x20 + c)
    t[#t + 1] = (v == 0x2C00) and '.' or string.format('%03X', v % 0x400)
  end
  return table.concat(t, ' ')
end
local function mapdump(tag)
  line('--- box map $7C00 ' .. tag)
  for _, r in ipairs({ 0, 1, 2, 3, 4, 5, 28, 29, 30, 31 }) do
    line(string.format('  r%02d %s', r, rowcells(r)))
  end
end
local function st()
  return string.format('F=%d 6E=%02X 6F=%02X 73=%02X 74=%02X 92=%02X 9E=%02X DD=%02X DF=%02X pend=%02X',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x0374), w(0x0392), w(0x039E),
    w(0x09DD), w(0x09DF), w(0x0BFB))
end
local pat = { 0x24CB, 0x24CE, 0x24D0, 0x24D2 }
local function poked()
  for _, r in ipairs({ 0, 1, 2, 3, 28, 29, 30, 31 }) do
    for c = 3, 28 do poke(0x7C00 + r * 0x20 + c, pat[(c % 4) + 1]) end
  end
end
local function advance(n)
  for _ = 1, n do
    -- run the state machine's step 22 ($03:F700, the fallback hook) directly:
    -- bit 4 of $0374 gates the handler table, $0392 is the step index.
    memory.write_u8(0x0374, w(0x0374) | 0x10, 'WRAM')
    memory.write_u8(0x0392, 22, 'WRAM')
    for _ = 1, 6 do emu.frameadvance() end
    memory.write_u8(0x0392, 0, 'WRAM')
    memory.write_u8(0x0374, w(0x0374) & 0xEF, 'WRAM')
    for _ = 1, 20 do emu.frameadvance() end
  end
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('rom ' .. ROMF .. ' state ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())

-- phase 1: base 28 -> rows 28..31
poked()
memory.write_u8(0x0BFB, 0x80 + 28, 'WRAM')
line('armed 28 ' .. st())
client.screenshot(TAG .. '_00_armed28')
mapdump('poked, armed base 28')
advance(1)
line('after one advance ' .. st())
mapdump('after base 28 wipe')
client.screenshot(TAG .. '_01_wiped28')

-- phase 2: base 0 -> rows 0..3
poked()
memory.write_u8(0x0BFB, 0x80 + 0, 'WRAM')
line('armed 0 ' .. st())
advance(1)
line('after one advance ' .. st())
mapdump('after base 0 wipe')
client.screenshot(TAG .. '_02_wiped0')

-- phase 3: no flag -> nothing must change
poked()
memory.write_u8(0x0BFB, 0, 'WRAM')
advance(1)
line('after no-flag advance ' .. st())
mapdump('no flag: rows must still be poked')
client.screenshot(TAG .. '_03_noflag')
line('done')
