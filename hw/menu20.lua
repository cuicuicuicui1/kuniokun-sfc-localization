-- menu20: does the band stub actually run?  Poke rows 28..31, then run the
-- engine's step 22 (which calls $03:FCC8, where the stub is hooked) and look.
local TAG  = os.getenv('HW_TAG') or 'menu20'
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
local function maprows(tag)
  line('--- rows 28..31 ' .. tag)
  for r = 28, 31 do line('  r' .. r .. ' ' .. rowcells(r)) end
end
local ok = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('state ' .. tostring(ok))
for _ = 1, 40 do emu.frameadvance() end
maprows('before poke')
local pat = { 0x24CB, 0x24CE, 0x24D0, 0x24D2 }
for r = 28, 31 do
  for c = 3, 28 do poke(0x7C00 + r * 0x20 + c, pat[(c % 4) + 1]) end
end
for _ = 1, 3 do emu.frameadvance() end
maprows('after poke')
-- run the engine's step 22: it calls $03:FCC8 (our band stub)
memory.write_u8(0x0374, w(0x0374) | 0x10, 'WRAM')
memory.write_u8(0x0392, 22, 'WRAM')
for i = 1, 40 do
  emu.frameadvance()
  if i % 10 == 0 then line(string.format('+%02d 92=%02X 74=%02X 6E=%02X DF=%02X', i, w(0x0392), w(0x0374), w(0x036E), w(0x09DF))) end
end
maprows('after step 22')
line('done')
