-- mesen_probe.lua: probe the Mesen2 Lua environment headlessly.
local ok, err
ok, err = pcall(function() emu.logMessage("probe: logMessage works") end)
if ok then print("LUA_PROBE logMessage OK") else print("LUA_PROBE logMessage FAIL: " .. tostring(err)) end
ok, err = pcall(function() local f = io.open("C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/mesen_probe_io.txt", "w") f:write("io works\n") f:close() end)
if ok then print("LUA_PROBE io OK") else print("LUA_PROBE io FAIL: " .. tostring(err)) end
ok, err = pcall(function() print("LUA_PROBE print OK frame=" .. tostring(emu.getFrameCount())) end)
if not ok then print("LUA_PROBE print FAIL: " .. tostring(err)) end
for _, name in ipairs({ "getProgramCounter", "getFrameCount", "addMemoryCallback", "setInput", "getRegisterValue", "read" }) do
  local t = type(emu[name])
  print("LUA_PROBE emu." .. name .. " = " .. t)
end
print("LUA_PROBE done")
