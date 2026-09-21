-- rep5: which 64 byte chunks of VRAM $C000..$FFFF are displayed at all?
--   For every chunk: reload the strip state, zero the chunk, advance one frame,
--   screenshot.  A chunk whose zeroing changes nothing on screen is not read by
--   the PPU in this scene (neither as a tile map row nor as tile data), so it is
--   a candidate home for the resident label tiles.
-- env: HW_TAG HW_SRAM HW_F
local TAG  = os.getenv('HW_TAG') or 'rep5'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local STATE = OUT .. (os.getenv('HW_STATE') or 'rep3_strip.state')
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local ok = pcall(function() savestate.load(STATE) end)
line('state load ' .. tostring(ok))
emu.frameadvance()
joypad.set({})
client.screenshot(TAG .. '_control')

for i = 0, 255 do
  local off = 0xC000 + i * 64
  local ok2 = pcall(function() savestate.load(STATE) end)
  if not ok2 then line('load failed at ' .. i); break end
  for a = 0, 63 do memory.write_u8(off + a, 0, 'VRAM') end
  joypad.set({})
  emu.frameadvance()
  client.screenshot(string.format('%s_c%03d_%04X', TAG, i, off))
  if i % 32 == 0 then line('chunk ' .. i) end
end
line('done')