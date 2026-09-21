-- openmenu: advance the story, then wait for an idle message box before pressing
-- Start, and as soon as the window's label table is populated dump everything.
local TAG = os.getenv('HW_TAG') or 'openmenu'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vw(a) return memory.read_u8(a*2,'VRAM') + memory.read_u8(a*2+1,'VRAM')*256 end
local function nz() local n=0 for k=0,51 do if w(0x040A+k)~=0 then n=n+1 end end return n end
while emu.framecount() < 1300 do emu.frameadvance() end
-- advance dialogue
for i = 1, 220 do
  for k = 0, 7 do joypad.set({A=true}); emu.frameadvance() end
  for k = 0, 22 do emu.frameadvance() end
  if nz() > 3 then break end
end
-- now try to open the window from an idle state
local opened = 0
for round = 1, 200 do
  for k = 0, 40 do emu.frameadvance() end          -- let any message finish
  for k = 0, 7 do joypad.set({Start=true}); emu.frameadvance() end
  for k = 0, 20 do emu.frameadvance() end
  if nz() > 3 then
    local r = w(0x036E)
    local base = (0x7C + math.floor(r/4)) * 0x100 + 0x03 + (r % 4) * 0x40
    local t, up, lo = {}, {}, {}
    for k = 0, 51 do t[#t+1] = string.format('%02X', w(0x040A+k)) end
    for k = 0, 25 do up[#up+1] = string.format('%04X', vw(base+k)) end
    for k = 0, 25 do lo[#lo+1] = string.format('%04X', vw(base+0x20+k)) end
    log:write(string.format('F=%d row=%02X col=%02X $039E=%02X\n', emu.framecount(), r, w(0x036F), w(0x039E)))
    log:write('  table: ' .. table.concat(t,' ') .. '\n')
    log:write('  upper: ' .. table.concat(up,' ') .. '\n')
    log:write('  lower: ' .. table.concat(lo,' ') .. '\n')
    log:write(string.format('  $039A=%02X $1BA6=%02X $01E5=%02X\n', w(0x039A), w(0x1BA6), w(0x01E5)))
    log:flush()
    client.screenshot(string.format('%s_%d', TAG, opened))
    opened = opened + 1
    if opened >= 2 then break end
    for k = 1, 40 do emu.frameadvance() end
  end
end
log:write('opened=' .. opened .. '\ndone\n'); log:flush()
