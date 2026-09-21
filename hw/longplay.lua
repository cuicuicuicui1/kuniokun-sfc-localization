-- longplay: tap through the story for a long stretch and grab a frame every
-- second, so a later scene (the one the user screenshotted) can be located.
-- env: HW_TAG HW_UNTIL
local TAG = os.getenv('HW_TAG') or 'longplay'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '30000') or 30000

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))

while emu.framecount() < UNTIL do
  local i = emu.framecount()
  -- advance dialogue
  if i % 30 < 8 then joypad.set({ A = true }) end
  -- walk right now and then, to leave the street
  if i > 2000 and i % 900 < 120 then joypad.set({ Right = true }) end
  if i % 60 == 0 then
    client.screenshot(string.format('%s_f%05d', TAG, i))
  end
  emu.frameadvance()
end
log:write('done F=' .. emu.framecount() .. '\n')
log:flush()