-- menu6: force the command window open.  Full chain (reverse engineered):
--   Start handler $00:F539 -> $0314 |= $80, $0363 = 3, JSL $03EB3D
--   $03EB3D -> $0373 |= $80, JSR $FD3C
--   $FD3C   -> $0374 |= $10, $0392 = $FD52[$0363] (= $26 for mode 3), $038F = 0
--   per frame the text state machine ($03:EE70 chain) calls $F0F1, which runs
--   the handler table at $F101 indexed by $0392 while $0374 bit 4 is set.
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'menu6'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function poke(a, v) memory.write_u8(a, v, 'WRAM') end
local function orr(a, v) poke(a, w(a) | v) end
local function nz() local n = 0 for k = 0, 51 do if w(0x040A + k) ~= 0 then n = n + 1 end end return n end
local function tbl()
  local t = {}
  for k = 0, 51 do t[#t + 1] = string.format('%02X', w(0x040A + k)) end
  return table.concat(t, ' ')
end
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function st()
  return string.format('F=%d 92=%02X 9E=%02X 91=%02X 6E=%02X 6F=%02X 63=%02X 73=%02X 74=%02X 68=%02X 14=%02X nz=%d dd=%02X df=%02X',
    emu.framecount(), w(0x0392), w(0x039E), w(0x0391), w(0x036E), w(0x036F), w(0x0363), w(0x0373),
    w(0x0374), w(0x0368), w(0x0314), nz(), w(0x09DD), w(0x09DF))
end
local function rows()
  local t = {}
  for r = 0, 7 do
    local s = {}
    for c = 0, 25 do s[#s + 1] = string.format('%03X', vw(0x7C00 + r * 0x20 + c) % 0x400) end
    t[#t + 1] = string.format('r%d %s', r, table.concat(s, ' '))
  end
  return table.concat(t, '\n')
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('load ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())
client.screenshot(TAG .. '_init')

-- what $03EB3D + $FD3C do, by hand
poke(0x0363, 3)
orr(0x0373, 0x80)
orr(0x0374, 0x10)
poke(0x0392, 0x26)
poke(0x038F, 0)
line('poked ' .. st())

for f = 1, 24 do
  for k = 0, 5 do emu.frameadvance() end
  line(string.format('  f%-2d %s', f, st()))
  client.screenshot(string.format('%s_%02d', TAG, f))
end
line('040A=' .. tbl())
line('rows:\n' .. rows())
line('done')
