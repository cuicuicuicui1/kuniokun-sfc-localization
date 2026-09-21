local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local log = assert(io.open(OUT .. 'api2.log', 'w'))
local function dump(name, t)
  local ks = {}
  for k, v in pairs(t) do if type(v) == 'function' then ks[#ks+1] = k end end
  table.sort(ks)
  log:write(name .. ': ' .. table.concat(ks, ' ') .. '\n')
end
dump('emu', emu); dump('client', client); dump('savestate', savestate); dump('memory', memory)
log:flush()
for _, n in ipairs({'reboot','softreset','reset','loadrom','openrom'}) do
  log:write('emu.' .. n .. ' = ' .. tostring(emu[n]) .. '\n')
end
for _, n in ipairs({'reboot_core','openrom','loadrom','screenshot'}) do
  log:write('client.' .. n .. ' = ' .. tostring(client[n]) .. '\n')
end
log:flush()
