-- menu12: poke the box content map ($7C00) rows 0-3 / 28-31 with the window
-- tiles (0xCB..0xE5, our hanzi) to simulate the leftovers, then advance the
-- dialogue and see which of those rows the engine rewrites on its own.
-- env: HW_TAG HW_ROM
local TAG  = os.getenv('HW_TAG') or 'menu12'
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
  return string.format('F=%d 6E=%02X 6F=%02X 73=%02X 74=%02X 91=%02X 92=%02X 9E=%02X DD=%02X DF=%02X',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x0374), w(0x0391), w(0x0392),
    w(0x039E), w(0x09DD), w(0x09DF))
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('rom ' .. ROMF .. ' state ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())
mapdump('before poke')

-- simulate the command window's leftovers: rows 0-3 and 28-31, columns 3..28
local pat = { 0x24CB, 0x24CE, 0x24D0, 0x24D2 }
for _, r in ipairs({ 0, 1, 2, 3, 28, 29, 30, 31 }) do
  for c = 3, 28 do poke(0x7C00 + r * 0x20 + c, pat[(c % 4) + 1]) end
end
for _ = 1, 3 do emu.frameadvance() end
line('after poke ' .. st())
client.screenshot(TAG .. '_00_poked')
mapdump('poked')

-- advance the dialogue a few times and watch
for round = 1, 6 do
  for _ = 1, 3 do joypad.set({ A = true }); emu.frameadvance() end
  joypad.set({})
  for _ = 1, 40 do emu.frameadvance() end
  line(string.format('round %d %s', round, st()))
  mapdump('after A ' .. round)
  client.screenshot(string.format('%s_%02d', TAG, round))
end
line('done')
