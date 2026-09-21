-- v29.lua : consecutive screenshots around the first dialogue, for a Python
--   template match of the expected glyphs over the whole visible screen.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v29"
local FROM = tonumber(os.getenv("HW_FROM") or "1383")
local TO = tonumber(os.getenv("HW_TO") or "1416")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

local idx = 0
while emu.framecount() < FROM do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
  emu.frameadvance()
end

while emu.framecount() <= TO do
  local f = emu.framecount()
  client.screenshot(string.format("%s/%s_f%05d.png", OUT, TAG, f))
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()
end
say(string.format("wrote frames %d..%d", FROM, TO))
log:close()