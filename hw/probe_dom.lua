-- probe: list memory domains, dump CGRAM at several frames, log sizes
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local log = assert(io.open(OUT .. 'probe_dom.log', 'w'))
pcall(function() emu.limitframerate(false) end)
local doms = memory.getmemorydomainlist()
for i, d in ipairs(doms) do log:write(i .. ': ' .. tostring(d) .. '\n') end
local frames = { [600] = true, [700] = true, [800] = true, [900] = true }
while emu.framecount() < 950 do
  local i = emu.framecount()
  if frames[i] then
    local ok, err = pcall(function()
      local f = assert(io.open(string.format(OUT .. 'cg%d.bin', i), 'wb'))
      for a = 0, memory.getmemorydomainsize('CGRAM') - 1 do
        f:write(string.char(memory.read_u8(a, 'CGRAM')))
      end
      f:close()
      log:write(string.format('F=%d cgram size=%d dumped\n', i, memory.getmemorydomainsize('CGRAM')))
    end)
    if not ok then log:write('F=' .. i .. ' cgram error: ' .. tostring(err) .. '\n') end
    log:flush()
  end
  if i == 150 or i == 300 then joypad.set({ Start = true }) end
  emu.frameadvance()
end
log:write('done\n')
log:flush()
