-- cbprobe: test whether BizHawk SNES memory-write callbacks fire, and whether
-- the PC is reachable inside the callback.  Logs to a file.
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local log = io.open(OUT .. 'cbprobe.log', 'w')
log:write('probe start\n')
log:flush()
local hits = 0
local function onwrite(addr, value)
  if hits < 40 then
    hits = hits + 1
    local pc = 'n/a'
    local ok, err = pcall(function() pc = string.format('%04X', emu.getRegisterValue('PC')) end)
    if not ok then pc = 'err:' .. tostring(err) end
    log:write(string.format('WRITE addr=%04X val=%02X pc=%s\n', addr, value, pc))
    if hits == 40 then log:write('...capped\n') end
    log:flush()
  end
end
local ok, err = pcall(function()
  event.onmemorywrite(onwrite, 0x03EA, 0x03ED, 'WRAM')
end)
log:write('onmemorywrite registered ok=' .. tostring(ok) .. ' err=' .. tostring(err) .. '\n')
log:flush()
while emu.framecount() < 2200 do
  if emu.framecount() == 150 or emu.framecount() == 300 or emu.framecount() == 450 then joypad.set({Start = true}) end
  if emu.framecount() >= 200 and emu.framecount() % 20 == 0 then joypad.set({A = true}) end
  emu.frameadvance()
end
log:write('done hits=' .. hits .. '\n')
log:flush()
