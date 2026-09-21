-- walkmenu: play the intro (tap A) until the field/walkable loop is live, then
-- press Start for real and check for the command window.  The Start handler is
-- $00:F539 and needs $0373 (text busy) == 0.
-- env: HW_TAG HW_UNTIL
local TAG = os.getenv('HW_TAG') or 'walkmenu'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '26000') or 26000
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function poke(a, v) memory.write_u8(a, v, 'WRAM') end
local function nz() local n = 0 for k = 0, 51 do if w(0x040A + k) ~= 0 then n = n + 1 end end return n end
local function tbl()
  local t = {}
  for k = 0, 51 do t[#t + 1] = string.format('%02X', w(0x040A + k)) end
  return table.concat(t, ' ')
end
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function st()
  return string.format('F=%d 92=%02X 9E=%02X 6E=%02X 63=%02X 73=%02X 74=%02X 68=%02X 14=%02X nz=%d',
    emu.framecount(), w(0x0392), w(0x039E), w(0x036E), w(0x0363), w(0x0373),
    w(0x0374), w(0x0368), w(0x0314), nz())
end
local function boxrows()
  local t = {}
  for r = 0, 6 do
    local s = {}
    for c = 0, 25 do s[#s + 1] = string.format('%03X', vw(0x7C00 + r * 0x20 + c) % 0x400) end
    t[#t + 1] = string.format('r%d %s', r, table.concat(s, ' '))
  end
  return table.concat(t, '\n')
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('load ok=' .. tostring(ok) .. ' ' .. tostring(err))

local won = false
local lastopen = -9999
while emu.framecount() < UNTIL and not won do
  local i = emu.framecount()
  -- tap A to walk the dialogue along, and wiggle the d-pad for the field loop
  if i % 20 == 0 and w(0x0373) ~= 0 then joypad.set({ A = true }) end
  if i % 40 == 10 then joypad.set({ Right = true }) end
  if i % 40 == 30 then joypad.set({ Left = true }) end
  -- every 300 frames try to open the menu the way a player would
  if i > 300 and i % 300 == 0 then
    line(string.format('try@%d %s', i, st()))
    for k = 1, 6 do joypad.set({ Start = true }); emu.frameadvance() end
    for k = 1, 20 do emu.frameadvance() end
    line(string.format('  after %s', st()))
    if w(0x0314) & 0x80 ~= 0 or w(0x0392) == 0x26 or nz() > 0 then
      won = true
      line('MENU OPEN? ' .. st())
      client.screenshot(TAG .. '_open')
      for k = 1, 40 do emu.frameadvance() end
      line('  +40f ' .. st())
      client.screenshot(TAG .. '_open40')
      line('040A=' .. tbl())
      line('box:\n' .. boxrows())
    end
  end
  if i % 4000 == 0 then client.screenshot(string.format('%s_f%05d', TAG, i)) end
  emu.frameadvance()
end
line('end ' .. st())
line('done')
