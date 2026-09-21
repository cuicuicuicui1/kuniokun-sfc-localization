-- hooktest.lua : figure out how hooks and register reads actually behave in this build
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local log = io.open(OUT .. "/hooktest.log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

say("can_use_callback_params=" .. tostring(event.can_use_callback_params))
say("availableScopes:")
pcall(function()
  for k, v in pairs(event.availableScopes()) do say("   " .. tostring(k) .. " = " .. tostring(v)) end
end)

-- register reads outside of a hook
local function try(s, f)
  local ok, v = pcall(f)
  say(string.format("%s ok=%s v=%s", s, tostring(ok), tostring(v)))
end
try('emu.getregister("A")', function() return emu.getregister("A") end)
try('emu.getregister("PC")', function() return emu.getregister("PC") end)
try('emu.getregister("PBR")', function() return emu.getregister("PBR") end)
try('emu.getregisters()', function() return emu.getregisters() end)
for i = 1, 30 do emu.frameadvance() end
try('emu.getregister("PC") after 30 frames', function() return emu.getregister("PC") end)
try('emu.getregister("A") after 30 frames', function() return emu.getregister("A") end)
local ok, regs = pcall(emu.getregisters)
if ok and type(regs) == "table" then
  local ks = {}
  for k, v in pairs(regs) do ks[#ks + 1] = tostring(k) .. "=" .. tostring(v) end
  say("registers: " .. table.concat(ks, " "))
end

-- do hooks fire? count hits on several candidate entry points
local counts = {}
local function mk(name)
  return function() counts[name] = (counts[name] or 0) + 1 end
end
local addrs = {
  { 0x03ED25, "loader_bus" }, { 0x03EEF5, "consumer_bus" }, { 0x03FA30, "drawer0_bus" },
  { 0x3E8200, "drawer1_bus" }, { 0x00833B, "int_00833B" }, { 0x01FC9E, "ctrl_bus" },
  { 0x80ED25, "loader_mirror" }, { 0x00B88C, "nmi_b88c" }, { 0x70B88C, "nmi_70" },
}
for _, a in ipairs(addrs) do
  local ok2, err = pcall(event.onmemoryexecute, mk(a[2]), a[1], a[2])
  say(string.format("hook %s @%06X ok=%s %s", a[2], a[1], tostring(ok2), tostring(err or "")))
end

local idx = 0
while emu.framecount() < 600 do
  idx = idx + 1
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
end
local ks = {}
for k, v in pairs(counts) do ks[#ks + 1] = k .. "=" .. v end
table.sort(ks)
say("hook hits: " .. table.concat(ks, " "))
log:close()