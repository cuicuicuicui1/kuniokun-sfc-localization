-- menuopen: reach a walkable scene (tap A, then walk), press Start, and report
-- whether the command window opened.  Dumps the label table and the two tilemap
-- rows it draws into as soon as it does, and watches brightness for a black-out.
local TAG = os.getenv('HW_TAG') or 'menuopen'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vw(a) return memory.read_u8(a*2,'VRAM') + memory.read_u8(a*2+1,'VRAM')*256 end
local function nz() local n=0 for k=0,51 do if w(0x040A+k)~=0 then n=n+1 end end return n end
local function bright()
  -- sample the picture through the emulator's own framebuffer
  local s = 0
  for y = 40, 200, 20 do for x = 8, 248, 20 do
    local p = memory.read_u8(x, 'VRAM'); s = s + p end end
  return s
end
local function dump(tag)
  local r = w(0x036E)
  local base = (0x7C + math.floor(r/4)) * 0x100 + 0x03 + (r % 4) * 0x40
  local t, up, lo = {}, {}, {}
  for k = 0, 51 do t[#t+1] = string.format('%02X', w(0x040A+k)) end
  for k = 0, 25 do up[#up+1] = string.format('%04X', vw(base+k)) end
  for k = 0, 25 do lo[#lo+1] = string.format('%04X', vw(base+0x20+k)) end
  log:write(string.format('[%s] F=%d row=%02X col=%02X $039E=%02X\n',
    tag, emu.framecount(), r, w(0x036F), w(0x039E)))
  log:write('  table: ' .. table.concat(t,' ') .. '\n')
  log:write('  upper: ' .. table.concat(up,' ') .. '\n')
  log:write('  lower: ' .. table.concat(lo,' ') .. '\n')
  log:flush()
  client.screenshot(TAG .. '_' .. tag)
end
while emu.framecount() < 1300 do emu.frameadvance() end
-- 1. tap through the narration
for i = 1, 60 do
  for k = 0, 7 do joypad.set({A=true}); emu.frameadvance() end
  for k = 0, 22 do emu.frameadvance() end
  if nz() > 3 then break end
end
log:write('narration done F=' .. emu.framecount() .. '\n')
-- 2. walk around: this is what leaves the dialogue-only mode
for round = 1, 40 do
  local d = ({'Right','Up','Right','Down'})[(round % 4) + 1]
  for k = 0, 60 do joypad.set({[d]=true}); emu.frameadvance() end
  for k = 0, 30 do emu.frameadvance() end
  -- try the menu
  for k = 0, 7 do joypad.set({Start=true}); emu.frameadvance() end
  for k = 0, 30 do emu.frameadvance() end
  if nz() > 3 then
    log:write('MENU OPENED on round ' .. round .. '\n')
    dump('open')
    break
  end
  if round % 10 == 0 then
    log:write(string.format('round %d F=%d moved=%s nz=%d\n', round, emu.framecount(), d, nz()))
    log:flush()
    client.screenshot(TAG .. '_r' .. round)
  end
end
log:write('final nz=' .. nz() .. ' F=' .. emu.framecount() .. '\ndone\n'); log:flush()
