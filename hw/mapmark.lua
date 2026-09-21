-- mapmark.lua: put a distinctive tile into one cell of a list of map rows, one
-- row per column, then screenshot.  Each marker's (x, y) on screen gives the
-- cell -> x and map row -> y mapping directly.
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v18.srm'
local AT   = tonumber(os.getenv('HW_AT') or '1400')
local TAG  = os.getenv('HW_TAG') or 'mm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end
local dirs = { 'Right', 'Left', 'Down', 'Up' }
for f = 1, AT do
  local k = f % 300
  local pad = {}
  if k < 3 or (k >= 30 and k < 33) or (k >= 170 and k < 174) then pad = { A = true }
  elseif k == 60 then pad = { Start = true }
  elseif k == 160 then pad = { B = true }
  elseif k >= 180 and k < 240 then pad = { [dirs[math.floor(f / 300) % 4 + 1]] = true } end
  joypad.set(pad); emu.frameadvance()
end
memory.usememorydomain('VRAM')
client.screenshot(TAG .. '_pre')
local rows = {0x7A80,0x7AA0,0x7AC0,0x7AE0,0x7B00,0x7B20,0x7B40,0x7B60,0x7B80,0x7BA0,0x7BC0,0x7BE0,0x7C00,0x7C20,0x7C40,0x7C60}
for i, base in ipairs(rows) do
  local cell = 2 + 2 * (i - 1)              -- one column per row, 2 apart
  local w = base + cell
  memory.write_u16_le(2 * w, 0x2453, 'VRAM')  -- tile $53, attr $24
  log:write(string.format('row %04X cell %d (word %04X)\n', base, cell, w))
end
log:flush()
for _ = 1, 4 do emu.frameadvance() end
client.screenshot(TAG .. '_shot')
log:write('done\n'); log:flush()
client.exit()
