-- cwdump: open the Start command window during gameplay and dump the two
-- tilemap rows it writes, plus the table cells and the row state.
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'cwdump'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vw(a) return memory.read_u8(a * 2, 'VRAM') + memory.read_u8(a * 2 + 1, 'VRAM') * 256 end
local function row(a, n)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format('%04X', vw(a + i)) end
  return table.concat(t, ' ')
end
while emu.framecount() < 1300 do emu.frameadvance() end
for i = 1, 40 do
  for k = 0, 7 do joypad.set({ A = true }); emu.frameadvance() end
  for k = 0, 22 do emu.frameadvance() end
end
-- open the command window
for i = 1, 4 do
  for k = 0, 7 do joypad.set({ Start = true }); emu.frameadvance() end
  for k = 0, 40 do emu.frameadvance() end
  local r = w(0x036E)
  local page = 0x7C + math.floor(r / 4)
  local low = 0x03 + (r % 4) * 0x40
  log:write(string.format('F=%d row=%02X page=%02X low=%02X  $039E=%02X $036F=%02X\n',
    emu.framecount(), r, page, low, w(0x039E), w(0x036F)))
  log:write('  upper: ' .. row(page * 0x100 + low, 26) .. '\n')
  log:write('  lower: ' .. row(page * 0x100 + low + 0x20, 26) .. '\n')
  local t = {}
  for i2 = 0, 51 do t[#t + 1] = string.format('%02X', w(0x040A + i2)) end
  log:write('  $040A: ' .. table.concat(t, ' ') .. '\n')
  log:flush()
end
client.screenshot(TAG .. '_menu')
log:write('done\n'); log:flush()
