local TAG = os.getenv('HW_TAG') or 'cwdump2'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vw(a) return memory.read_u8(a*2,'VRAM') + memory.read_u8(a*2+1,'VRAM')*256 end
while emu.framecount() < 1300 do emu.frameadvance() end
local opened = 0
for round = 1, 900 do
  local i = emu.framecount()
  if i % 24 < 6 then joypad.set({ Start = true }) end
  if i % 60 < 5 then joypad.set({ A = true }) end
  -- has the window opened?  its label table is copied to WRAM $040A
  local nz = 0
  for k = 0, 51 do if w(0x040A + k) ~= 0 then nz = nz + 1 end end
  if nz > 3 then
    local t = {}
    for k = 0, 51 do t[#t+1] = string.format('%02X', w(0x040A + k)) end
    log:write(string.format('F=%d row=%02X col=%02X table=%s\n',
      i, w(0x036E), w(0x036F), table.concat(t, ' ')))
    local r = w(0x036E)
    local base = (0x7C + math.floor(r/4)) * 0x100 + 0x03 + (r % 4) * 0x40
    local up, lo = {}, {}
    for k = 0, 25 do up[#up+1] = string.format('%04X', vw(base + k)) end
    for k = 0, 25 do lo[#lo+1] = string.format('%04X', vw(base + 0x20 + k)) end
    log:write('  up: ' .. table.concat(up, ' ') .. '\n')
    log:write('  lo: ' .. table.concat(lo, ' ') .. '\n')
    log:flush()
    client.screenshot(string.format('%s_open%d', TAG, opened))
    opened = opened + 1
    if opened >= 3 then break end
    for k = 1, 30 do emu.frameadvance() end
  end
  emu.frameadvance()
end
log:write('opened=' .. opened .. '\ndone\n'); log:flush()
