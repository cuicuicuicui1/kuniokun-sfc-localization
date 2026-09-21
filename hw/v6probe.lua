-- v6probe: tap through the opening so messages that call the hero by name are
-- on screen, and grab the box every second.
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'v6probe'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
while emu.framecount() < 1300 do emu.frameadvance() end
for i = 1, 60 do
  for k = 0, 7 do joypad.set({A = true}); emu.frameadvance() end
  for k = 0, 22 do emu.frameadvance() end
  client.screenshot(string.format('%s_f%05d', TAG, emu.framecount()))
end
log:write('done F=' .. emu.framecount() .. '\n'); log:flush()
