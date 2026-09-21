-- vrammark: fill each 8KB block of VRAM with a distinct solid colour index, then
-- screenshot.  Diffing against the untouched frame shows which VRAM area is
-- displayed where -- no PPU registers or CGRAM needed.
-- env: HW_TAG HW_ROM
local TAG  = os.getenv('HW_TAG') or 'vrammark'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local AT   = tonumber(os.getenv('HW_AT') or '700') or 700

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))

local function shot(name)
  client.screenshot(string.format('%s_f%05d_%s.png', TAG, emu.framecount(), name))
end

while emu.framecount() < AT do emu.frameadvance() end
shot('base')
log:write('F=' .. emu.framecount() .. ' baseline\n')

-- 8 KB per region, 8 regions; region r gets colour index r+1 in every bitplane
-- nibble/byte so it shows up at any bpp.
for r = 0, 7 do
  local v = r + 1
  local fill = v * 0x11
  for i = 0, 0x1FFF do
    memory.write_u8(r * 0x2000 + i, fill)
  end
end
emu.frameadvance()
emu.frameadvance()
shot('mark')
log:write('F=' .. emu.framecount() .. ' marked\n')
log:write('done\n')
log:flush()