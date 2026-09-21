-- menuopen2: progress the story WITHOUT pressing Start (at the title screen
-- Start just begins a new game, which is what kept resetting the run).  The HUD
-- name plate is only drawn in the walkable scenes, so its tilemap word at $79C6
-- is the signal that Start will now open the command window.
local TAG = os.getenv('HW_TAG') or 'menuopen2'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vw(a) return memory.read_u8(a*2,'VRAM') + memory.read_u8(a*2+1,'VRAM')*256 end
local function nz() local n=0 for k=0,51 do if w(0x040A+k)~=0 then n=n+1 end end return n end
local function hud() local n=0 for k=0,0x1C0,0x20 do if vw(0x79C0+k) ~= 0 then n=n+1 end end return n end
local function dump(tag)
  local r = w(0x036E)
  local base = (0x7C + math.floor(r/4)) * 0x100 + 0x03 + (r % 4) * 0x40
  local t, up, lo = {}, {}, {}
  for k = 0, 51 do t[#t+1] = string.format('%02X', w(0x040A+k)) end
  for k = 0, 25 do up[#up+1] = string.format('%04X', vw(base+k)) end
  for k = 0, 25 do lo[#lo+1] = string.format('%04X', vw(base+0x20+k)) end
  log:write(string.format('[%s] F=%d row=%02X col=%02X $039E=%02X hud=%d\n',
    tag, emu.framecount(), r, w(0x036F), w(0x039E), hud()))
  log:write('  table: ' .. table.concat(t,' ') .. '\n')
  log:write('  upper: ' .. table.concat(up,' ') .. '\n')
  log:write('  lower: ' .. table.concat(lo,' ') .. '\n')
  log:flush(); client.screenshot(TAG .. '_' .. tag)
end
while emu.framecount() < 1300 do emu.frameadvance() end
-- advance with A only, and walk; never touch Start while the title may be up
for i = 1, 120 do
  for k = 0, 7 do joypad.set({A=true}); emu.frameadvance() end
  for k = 0, 22 do emu.frameadvance() end
  if i % 15 == 0 then
    local d = ({'Right','Up','Right','Down'})[((i // 15) % 4) + 1]
    for k = 0, 70 do joypad.set({[d]=true}); emu.frameadvance() end
  end
  if hud() >= 3 then log:write('HUD seen at F=' .. emu.framecount() .. '\n'); break end
end
log:write(string.format('after story F=%d hud=%d\n', emu.framecount(), hud())); log:flush()
-- now Start is safe
for round = 1, 12 do
  for k = 0, 7 do joypad.set({Start=true}); emu.frameadvance() end
  for k = 0, 40 do emu.frameadvance() end
  log:write(string.format('round %d F=%d nz=%d hud=%d\n', round, emu.framecount(), nz(), hud()))
  if nz() > 3 then log:write('MENU OPENED\n'); dump('open'); break end
  log:flush()
end
client.screenshot(TAG .. '_end')
log:write('done nz=' .. nz() .. '\n'); log:flush()
