-- v11.lua : one-frame-resolution A/B dump around the point where the dialogue
-- text starts being drawn (frame ~1382 in both ROMs).  Gives the exact frame at
-- which the patched ROM diverges from the original, plus the stack page (the
-- only view of the call chain available, since this core exposes no PC).
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v11"
local FROM = tonumber(os.getenv("HW_FROM") or "1350")
local TO = tonumber(os.getenv("HW_TO") or "1500")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end
local function hexrange(a, n)
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.format("%02X", rd(a + i)) end
  return table.concat(t, " ")
end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
local idx = 0
while emu.framecount() < TO do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
  emu.frameadvance()
  local f = emu.framecount()
  if f >= FROM then
    say(string.format("F=%d len=%02X idx=%02X col=%02X row=%02X stage=%02X flag=%02X 0011=%02X 036D=%02X 0362=%02X 0363=%02X 0371=%02X 0373=%02X 03A9=%02X",
      f, rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x036E), rd(0x09DF), rd(0x0374), rd(0x0011),
      rd(0x036D), rd(0x0362), rd(0x0363), rd(0x0371), rd(0x0373), rd(0x03A9)))
    say("   msg " .. hexrange(0x03EA, 20))
    say("   scr " .. hexrange(0x0B00, 24))
    say("   stk " .. hexrange(0x01E0, 32))
    say("   ins " .. hexrange(0x0BE0, 11))
  end
end
say("done frame=" .. emu.framecount())
log:close()