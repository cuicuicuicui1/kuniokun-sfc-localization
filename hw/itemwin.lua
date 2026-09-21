-- itemwin: does the item window ever draw?
--
-- The bank $01 routine at $01:F7CC draws three item names from the pointer
-- table at $03DBC3 into the tile map cells $79C6 / $7A06 / $7A46, and the game's
-- own start menu offers "どうぐをつかう" (use item).  This probe opens that menu
-- and walks the cursor, watching those three cells plus the state bytes the
-- window routine uses, so we can see whether it ever runs.
--
-- env: HW_TAG HW_SRAM HW_NF
local TAG  = os.getenv('HW_TAG') or 'itemwin'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kuniokun_ORIGINAL.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local NF   = tonumber(os.getenv('HW_NF') or '2400')
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vw(a) return memory.read_u8(a, 'VRAM') end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
else
  line('NO SRAM ' .. SRAM)
end
client.reboot_core()
for _ = 1, 180 do emu.frameadvance() end

-- the three cursors the item window writes, in VRAM bytes
local CELLS = { { 0x79C6, 0xF38C }, { 0x7A06, 0xF40C }, { 0x7A46, 0xF48C } }
local function cellbytes()
  local t = {}
  for _, c in ipairs(CELLS) do
    local s = {}
    for i = 0, 7 do s[#s + 1] = string.format('%02X', vw(c[2] + i)) end
    t[#t + 1] = table.concat(s, '')
  end
  return table.concat(t, ' ')
end

local last = cellbytes()
line('cells at start: ' .. last)

local function step(label, pad, frames)
  joypad.set(pad)
  emu.frameadvance()
  joypad.set({})
  for _ = 1, (frames or 12) do emu.frameadvance() end
  local c = cellbytes()
  local mark = (c ~= last) and '  <-- CELLS CHANGED' or ''
  last = c
  line(string.format('%-22s 1BA6=%02X 1BA5=%02X 1BA7=%02X DE1=%02X DE3=%02X DE5=%02X DE7=%02X DE9=%02X DED=%02X 1B5A=%02X 1B5B=%02X  E5=%02X%02X%02X E7=%02X%02X%02X E9=%02X%02X%02X  %s%s',
    label, w(0x1BA6), w(0x1BA5), w(0x1BA7), w(0x0DE1), w(0x0DE3), w(0x0DE5), w(0x0DE7),
    w(0x0DE9), w(0x0DED), w(0x1B5A), w(0x1B5B),
    w(0x01E5), w(0x01E6), w(0x01E7), w(0x01E8), w(0x01E9), w(0x01EA),
    w(0x01EB), w(0x01EC), w(0x01ED), c, mark))
  client.screenshot(TAG .. '_' .. label)
end

step('00_idle', {}, 30)
step('01_start', { Start = true }, 30)
step('02_right', { Right = true }, 20)
step('03_A', { A = true }, 40)
step('04_A_again', { A = true }, 40)
step('05_B', { B = true }, 30)
step('06_B_again', { B = true }, 30)

-- second attempt: Start, then walk down/right over every menu cell and press A
step('07_start', { Start = true }, 30)
for i = 1, 4 do
  step(string.format('08_down%d', i), { Down = true }, 12)
  step(string.format('09_A%d', i), { A = true }, 30)
  step(string.format('10_B%d', i), { B = true }, 20)
end

-- watch a while for any change
local changed = 0
for f = 1, 600 do
  emu.frameadvance()
  local c = cellbytes()
  if c ~= last then
    changed = changed + 1
    line(string.format('CELLS CHANGED at f=%d -> %s  DE1=%02X 1BA6=%02X', f, c, w(0x0DE1), w(0x1BA6)))
    last = c
  end
end
line('watch done, changes=' .. changed)
client.screenshot(TAG .. '_final')
line('done')
