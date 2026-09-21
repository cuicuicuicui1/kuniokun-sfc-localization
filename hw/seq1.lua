-- seq1: how often does $03:FCC8 fire?  The debug build's stub increments $0bf9
-- there.  Drive a dialogue and log the counter next to the text row/column.
local TAG  = os.getenv('HW_TAG') or 'seq1'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v12.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local F0   = tonumber(os.getenv('HW_F0') or '2400')
local F1   = tonumber(os.getenv('HW_F1') or '3300')
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function w(a) return memory.read_u8(a, 'WRAM') end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end

local dirs = { 'Right', 'Left', 'Down', 'Up' }
for f = 1, F1 do
  local k = f % 300
  local pad = {}
  if k < 3 or (k >= 30 and k < 33) or (k >= 170 and k < 174) then
    pad = { A = true }
  elseif k == 60 then
    pad = { Start = true }
  elseif k == 160 then
    pad = { B = true }
  elseif k >= 180 and k < 240 then
    pad = { [dirs[math.floor(f / 300) % 4 + 1]] = true }
  end
  joypad.set(pad)
  emu.frameadvance()
  if f >= F0 then
    line(string.format('f%05d cnt=%3d 6E=%02X 6F=%02X 74=%02X 91=%02X 92=%02X 9E=%02X',
      f, w(0x0BF9), w(0x036E), w(0x036F), w(0x0374), w(0x0391), w(0x0392), w(0x039E)))
  end
end
line('done')