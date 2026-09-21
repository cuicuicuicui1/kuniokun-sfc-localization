local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local log = assert(io.open(OUT .. 'domains.log', 'w'))
for _, n in ipairs(memory.getmemorydomainlist()) do
  log:write(string.format('%s size=%d\n', tostring(n), memory.getmemorydomainsize(n)))
end
log:flush()
client.exit()
