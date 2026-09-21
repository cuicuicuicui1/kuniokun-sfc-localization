-- v13.lua : read the instrumentation counters around the freeze point.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v13"
local FROM = tonumber(os.getenv("HW_FROM") or "1370")
local TO = tonumber(os.getenv("HW_TO") or "1400")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function r(a) return memory.read_u8(a, "WRAM") end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
local idx = 0
while emu.framecount() < TO do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()
  local f = emu.framecount()
  if f >= FROM then
    say(string.format("F=%d len=%02X idx=%02X col=%02X row=%02X stage=%02X flag=%02X drv=%02X%02X draw=%02X caller=%02X%02X 12in=%02X Ain=%02X 0373=%02X",
      f, r(0x03E8), r(0x03E9), r(0x036F), r(0x036E), r(0x09DF), r(0x0374),
      r(0x0C01), r(0x0C00), r(0x0C0D), r(0x0C0F), r(0x0C0E), r(0x0C10), r(0x0C11), r(0x0373)))
    say(string.format("   cnbe  code=%02X idxin=%02X colin=%02X dbr=%02X idxout=%02X colout=%02X cnt=%02X",
      r(0x0BE0), r(0x0BE1), r(0x0BE2), r(0x0BE3), r(0x0BE4), r(0x0BE5), r(0x0BE6)))
    say(string.format("   msg %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X",
      r(0x03EA), r(0x03EB), r(0x03EC), r(0x03ED), r(0x03EE), r(0x03EF), r(0x03F0),
      r(0x03F1), r(0x03F2), r(0x03F3), r(0x03F4), r(0x03F5), r(0x03F6), r(0x03F7),
      r(0x03F8), r(0x03F9)))
  end
end
say("done frame=" .. emu.framecount())
log:close()