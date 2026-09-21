-- probe.lua : find out which BizHawk Lua APIs actually work for this core
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local log = io.open(OUT .. "/probe.log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

say("system=" .. tostring(emu.getsystemid()))
for i = 1, 5 do emu.frameadvance() end

for _, n in ipairs({ "PC", "pc", "A", "X", "Y", "S", "D", "DB", "PBR", "P", "C", "K" }) do
  local ok, v = pcall(memory.getregister, n)
  say(string.format("getregister(%s) ok=%s v=%s", n, tostring(ok), tostring(v)))
end
for _, d in ipairs({ "WRAM", "System Bus", "CARTROM", "VRAM", "Main RAM", "SNES WRAM" }) do
  local ok, v = pcall(memory.read_u8, 0x036E, d)
  say(string.format("read_u8(036E,%s) ok=%s v=%s", d, tostring(ok), tostring(v)))
end
local ok, v = pcall(memory.getcurrentmemorydomainsize, "System Bus")
say("System Bus size ok=" .. tostring(ok) .. " v=" .. tostring(v))
local out = {}
pcall(function()
  for _, d in pairs(memory.getmemorydomainlist()) do out[#out + 1] = d end
end)
say("domains: " .. table.concat(out, ", "))
say("framecount=" .. tostring(emu.framecount()))
log:close()