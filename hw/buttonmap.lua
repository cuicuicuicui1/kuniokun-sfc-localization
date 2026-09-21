-- buttonmap: reach gameplay, then press one button at a time and sample frames, so
-- each button's action can be read off the screen.
-- env: HW_TAG HW_AT
local TAG = os.getenv('HW_TAG') or 'buttonmap'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local AT  = tonumber(os.getenv('HW_AT') or '1400') or 1400

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))

-- (joypad table field, label)
local buttons = {
  {'A', 'A'}, {'B', 'B'}, {'X', 'X'}, {'Y', 'Y'},
  {'L', 'L'}, {'R', 'R'}, {'Select', 'SEL'}, {'Start', 'STA'},
}

while emu.framecount() < AT do emu.frameadvance() end

for _, b in ipairs(buttons) do
  local key, label = b[1], b[2]
  for k = 0, 27 do
    local t = {}
    t[key] = true
    joypad.set(t)
    if k % 4 == 0 then
      client.screenshot(string.format('%s_%s_%02d', TAG, label, k))
    end
    emu.frameadvance()
  end
  for k = 0, 11 do emu.frameadvance() end
  log:write(label .. ' done at F=' .. emu.framecount() .. '\n')
  log:flush()
end
log:write('done\n')
log:flush()