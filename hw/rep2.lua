-- rep2: same drive as rep1, but dump VRAM every 8 frames across the window in
-- which the strip appears (f=2400..2800), so consecutive dumps can be diffed and
-- the write that creates the strip can be located.
-- env: HW_TAG HW_SRAM
local TAG  = os.getenv('HW_TAG') or 'rep2'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v12.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local NF   = tonumber(os.getenv('HW_NF') or '3000')
local F0   = tonumber(os.getenv('HW_F0') or '2400')
local F1   = tonumber(os.getenv('HW_F1') or '2800')
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end

local function rows(base, r0, r1, n)
  local out = {}
  for r = r0, r1 do
    local t = {}
    for c = 0, n - 1 do
      local v = vw(base + r * 0x20 + c)
      t[#t + 1] = (v == 0x2C00) and '.' or string.format('%03X', v % 0x400)
    end
    out[#out + 1] = string.format('r%02d %s', r, table.concat(t, ' '))
  end
  return table.concat(out, '\n')
end

local dirs = { 'Right', 'Left', 'Down', 'Up' }
for f = 1, NF do
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
  if f % 8 == 0 and f >= F0 and f <= F1 then
    local g = assert(io.open(string.format('%s_%05d_vram.bin', TAG, f), 'wb'))
    for a = 0, 65535 do g:write(string.char(vb(a))) end
    g:close()
    client.screenshot(string.format('%s_%05d', TAG, f))
    line(string.format('f%05d 6E=%02X 74=%02X 92=%02X 9E=%02X DF=%02X DD=%02X',
      f, w(0x036E), w(0x0374), w(0x0392), w(0x039E), w(0x09DF), w(0x09DD)))
  end
  if f == F1 then
    line('--- map $7C00 rows 14..24 at end of window')
    line(rows(0x7C00, 14, 24, 32))
    local h = assert(io.open(OUT .. TAG .. '_wram.bin', 'wb'))
    for a = 0, 0x1FFF do h:write(string.char(w(a))) end
    h:close()
    local c = assert(io.open(OUT .. TAG .. '_cgram.bin', 'wb'))
    for a = 0, 511 do c:write(string.char(memory.read_u8(a, 'CGRAM'))) end
    c:close()
  end
end
line('done')