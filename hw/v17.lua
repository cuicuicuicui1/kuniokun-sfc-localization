-- v17.lua : find the stored text behind the first dialogue.  Watches the long
-- indirect source pointer ($22/$23/$24) that the loader walks while it copies a
-- message into the RAM buffer at $03EA, so the stored bytes can be located in
-- the ROM instead of guessed at.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v17"
local FROM = tonumber(os.getenv("HW_FROM") or "1370")
local TO = tonumber(os.getenv("HW_TO") or "1400")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
local idx = 0
local seen = {}
while emu.framecount() < TO do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()
  local f = emu.framecount()
  if f >= FROM then
    local p = rd(0x22) + rd(0x23) * 256 + rd(0x24) * 65536
    local buf = {}
    for k = 0, 23 do buf[#buf + 1] = string.format("%02X", rd(0x03EA + k)) end
    say(string.format(
      "F=%d ptr=%06X (lo=%02X hi=%02X bk=%02X) e8=%02X e9=%02X w11=%02X w10=%02X y=%02X",
      f, p, rd(0x22), rd(0x23), rd(0x24), rd(0x03E8), rd(0x03E9), rd(0x11), rd(0x10), rd(0x2A)))
    say("   buf=" .. table.concat(buf, " "))
  end
end