-- vrampoke: decide whether Lua writes into the VRAM domain actually reach the
-- rendered picture, and where each VRAM area lands on screen.
-- Phase A: screenshots with no writes, to measure natural frame variation.
-- Phase B: for a list of byte offsets, stamp a solid block, shoot, restore, shoot.
-- env: HW_TAG HW_ROM
local TAG = os.getenv('HW_TAG') or 'vrampoke'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local AT  = tonumber(os.getenv('HW_AT') or '900') or 900

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function shot(n) client.screenshot(string.format('%s_f%05d_%s.png', TAG, emu.framecount(), n)) end

while emu.framecount() < AT do emu.frameadvance() end

-- Phase A: watch several frames untouched.
for k = 0, 4 do
  shot(string.format('a%d', k))
  emu.frameadvance()
end
log:write('phase A done\n')

-- keep a copy of all of VRAM so each stamp can be undone
local copy = {}
for i = 0, 0xFFFF do copy[i] = memory.read_u8(i, 'VRAM') end
local function restore()
  for i = 0, 0xFFFF do memory.write_u8(i, copy[i], 'VRAM') end
end

-- Phase B: stamp a solid 32-byte tile at these byte offsets, one at a time.
local sites = {0x0000, 0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x6000, 0x6100,
               0x7000, 0x7100, 0x8000, 0x8100, 0x9000, 0xA000, 0xC000, 0xD000}
for _, o in ipairs(sites) do
  for i = 0, 0x1F do memory.write_u8(o + i, 0xFF, 'VRAM') end
  emu.frameadvance()
  emu.frameadvance()
  shot(string.format('mark%04X', o))
  restore()
  emu.frameadvance()
  local same = 1
  log:write(string.format('stamped %04X\n', o))
end
log:write('done\n')
log:flush()