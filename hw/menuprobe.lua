-- menuprobe.lua: drive until the pause menu actually opens, then dump VRAM
-- repeatedly while it is open.
--
-- The question this answers: the command window's five labels are drawn once
-- and then have to stay on screen.  If the game draws nothing else while the
-- menu is open, the labels can be drawn by our own drawer out of the glyph pool
-- (no extra tile pairs at all); if something else does draw, its glyph uploads
-- would land in the pool slots the labels are using.
--
-- The menu is detected through the command window's cell table: the copier at
-- $03:F940 writes 52 bytes of label codes to $040A when it opens, and the
-- close stub clears it again.
--
-- env: HW_TAG HW_SRAM HW_NF
local TAG  = os.getenv('HW_TAG') or 'mp'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v19.srm'
local NF   = tonumber(os.getenv('HW_NF') or '12000')
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end

local function vram() return memory.read_bytes_as_array(0, 65536, 'VRAM') end
local function dump(name, a)
  local f = assert(io.open(OUT .. name, 'wb'))
  local t = {}
  for i = 1, #a do t[i] = string.char(a[i]) end
  f:write(table.concat(t)); f:close()
end

local seen, first = 0, nil
for f = 1, NF do
  local k = f % 240
  local pad = {}
  if k % 20 < 3 then pad = { A = true } end        -- advance dialogue
  if k == 100 or k == 130 then pad = { Start = true } end
  if k == 180 then pad = { B = true } end
  joypad.set(pad)
  emu.frameadvance()
  if f % 1000 == 0 then
    line(string.format('progress f=%d 0364=%02X%02X%02X 036E=%02X 036F=%02X',
         f, memory.read_u8(0x0364,'WRAM'), memory.read_u8(0x0365,'WRAM'),
         memory.read_u8(0x0366,'WRAM'), memory.read_u8(0x036E,'WRAM'),
         memory.read_u8(0x036F,'WRAM')))
  end
  if f % 10 == 0 then
    local tab = memory.read_bytes_as_array(0x040A, 52, 'WRAM')
    local nz = 0
    for i = 1, 52 do if tab[i] ~= 0 then nz = nz + 1 end end
    if nz > 4 then
      seen = seen + 1
      if seen <= 40 then
        dump(string.format('%s_%05d.vram', TAG, f), vram())
        dump(string.format('%s_%05d.wram', TAG, f), memory.read_bytes_as_array(0, 4096, 'WRAM'))
      end
      if seen == 1 then first = f end
      line(string.format('menu at frame %d (nz=%d) 0392=%02X 0395=%02X 03B7=%02X',
           f, nz, memory.read_u8(0x0392, 'WRAM'), memory.read_u8(0x0395, 'WRAM'),
           memory.read_u8(0x03B7, 'WRAM')))
    end
  end
end
line('done, menu frames seen: ' .. seen .. (first and (' first ' .. first) or ''))
client.exit()
