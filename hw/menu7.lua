-- menu7: same as menu6, but keep $0314 bit 7 (the "UI panel open" flag the
-- driver at $00:F539 clears and re-checks every frame) set while the script
-- runs, so the per-frame text engine ($03EE70 chain -> $F0F1 -> step $0392)
-- actually executes the window script.
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'menu7'
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
  return string.format('F=%d 92=%02X 9E=%02X 91=%02X 6E=%02X 6F=%02X 63=%02X 73=%02X 74=%02X 68=%02X 14=%02X 9A=%02X nz=%d dd=%02X df=%02X',
    emu.framecount(), w(0x0392), w(0x039E), w(0x0391), w(0x036E), w(0x036F), w(0x0363), w(0x0373),
    w(0x0374), w(0x0368), w(0x0314), w(0x039A), nz(), w(0x09DD), w(0x09DF))
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

poke(0x0363, 3)
orr(0x0373, 0x80)
poke(0x0392, 0x26)
poke(0x038F, 0)
line('poked ' .. st())

for f = 1, 20 do
  for k = 0, 5 do
    orr(0x0314, 0x80)
    orr(0x0374, 0x10)
    emu.frameadvance()
  end
  line(string.format('  f%-2d %s', f, st()))
  client.screenshot(string.format('%s_%02d', TAG, f))
end
line('040A=' .. tbl())
line('rows:\n' .. rows())

-- now press A / down / A to see the input handler react, still holding the flag
for f = 1, 12 do
  local btn = (f % 4 == 1) and { A = true } or (f % 4 == 3) and { Down = true } or {}
  for k = 0, 5 do
    orr(0x0314, 0x80); orr(0x0374, 0x10)
    if next(btn) then joypad.set(btn) end
    emu.frameadvance()
  end
  line(string.format('  k%-2d %s', f, st()))
  client.screenshot(string.format('%s_k%02d', TAG, f))
end
line('done')
