-- titlestart: sit on the title screen past the intro, press Start, and sample the
-- frames that follow, to settle whether an opening menu exists or the game goes
-- straight into the story.
-- env: HW_TAG HW_ROM
local TAG = os.getenv('HW_TAG') or 'titlestart'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))

local PRESS = tonumber(os.getenv('HW_AT') or '1200') or 1200
while emu.framecount() < PRESS + 400 do
  local i = emu.framecount()
  if i >= PRESS and i <= PRESS + 8 then joypad.set({ Start = true }) end
  if i >= PRESS + 40 and i <= PRESS + 44 then joypad.set({ A = true }) end
  if i % 10 == 0 then
    client.screenshot(string.format('%s_f%05d.png', TAG, i))
  end
  emu.frameadvance()
end
log:write('pressed Start at ' .. PRESS .. '\n')
log:write('done\n')
log:flush()