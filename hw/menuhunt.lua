-- menuhunt: after the opening dialogues, tap Start periodically and screenshot
-- every 30 frames, hunting for the pause/item window layout.
-- env: HW_TAG HW_UNTIL
local TAG = os.getenv('HW_TAG') or 'menuhunt'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '4200') or 4200
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local starts = { [1000] = true, [1600] = true, [2200] = true, [2800] = true, [3400] = true }
local held = 0
while emu.framecount() < UNTIL do
  local i = emu.framecount()
  if i == 150 or i == 300 or i == 450 then joypad.set({ Start = true }) end
  if i >= 200 and i % 20 == 0 then joypad.set({ A = true }) end
  if starts[i] then held = 6 end
  if held > 0 then
    joypad.set({ Start = true })
    held = held - 1
  end
  if i >= 900 and i % 30 == 0 then
    client.screenshot(string.format('%s_f%05d.png', TAG, i))
  end
  emu.frameadvance()
end
log:write('done\n')
log:flush()
