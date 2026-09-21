-- api.lua : list the keys available in the Lua API tables of this BizHawk build
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local log = io.open(OUT .. "/api.log", "w")
local function keys(name, t)
  if type(t) ~= "table" then log:write(name .. ": <" .. type(t) .. ">\n"); return end
  local ks = {}
  for k, v in pairs(t) do ks[#ks + 1] = tostring(k) .. ":" .. type(v) end
  table.sort(ks)
  log:write(name .. " (" .. #ks .. "): " .. table.concat(ks, " ") .. "\n\n")
end
keys("memory", memory)
keys("emu", emu)
keys("event", event)
keys("joypad", joypad)
keys("client", client)
keys("gui", gui)
keys("savestate", savestate)
keys("debugger", debugger)
keys("movie", movie)
keys("console", console)
keys("mainmemory", mainmemory)
keys("gameinfo", gameinfo)
log:write("bizhawk version: " .. tostring(client.getversion and client.getversion()) .. "\n")
log:close()