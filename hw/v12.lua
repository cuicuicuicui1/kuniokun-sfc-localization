-- v12.lua : dump the WHOLE 65816 stack page ($0100-$01FF) every frame around the
-- divergence, so the return-address chain reveals where each ROM's execution is.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v12"
local FROM = tonumber(os.getenv("HW_FROM") or "1378")
local TO = tonumber(os.getenv("HW_TO") or "1394")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rb(a, d) return memory.read_u8(a, d or "WRAM") end
local function hexrange(a, n, d)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format("%02X", rb(a + i, d)) end
  return table.concat(t, " ")
end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
local idx = 0
while emu.framecount() < TO do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()
  local f = emu.framecount()
  if f >= FROM then
    say(string.format("F=%d len=%02X idx=%02X col=%02X row=%02X stage=%02X flag=%02X 0011=%02X 036D=%02X",
      f, rb(0x03E8), rb(0x03E9), rb(0x036F), rb(0x036E), rb(0x09DF), rb(0x0374), rb(0x0011), rb(0x036D)))
    say("   msg " .. hexrange(0x03EA, 20))
    say("   stk " .. hexrange(0x0100, 256))
    -- PPU state: is the screen ever finished/blanked, is NMI alive
    say("   ppu 2100=" .. string.format("%02X", rb(0x2100, "System Bus")) ..
        " 4210=" .. string.format("%02X", rb(0x4210, "System Bus")) ..
        " 4211=" .. string.format("%02X", rb(0x4211, "System Bus")) ..
        " 4212=" .. string.format("%02X", rb(0x4212, "System Bus")))
  end
end
say("done frame=" .. emu.framecount())
log:close()