-- v27.lua : locate the on-screen rectangle of one dialogue cell and dump it.
--   Play with the deterministic input sequence up to HW_AT (default 1398, i.e.
--   just after the first dialogue has been drawn), screenshot A, poke a solid
--   pattern into the VRAM tile used by the 5th column cell of that dialogue
--   (tile 0x9C, VRAM byte 0xC9C0), advance one frame, screenshot B.  The pixel
--   difference A vs B is that cell's rectangle on screen, which the Python side
--   then compares against the glyph pool bytes of that character.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v27"
local AT = tonumber(os.getenv("HW_AT") or "1398")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

local function hexfrom(a, n)
  local t = {}
  for k = 0, n - 1 do t[#t + 1] = string.format("%02X", memory.read_u8(a + k, "VRAM")) end
  return table.concat(t, " ")
end

local idx = 0
while emu.framecount() < AT do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
  emu.frameadvance()
end

say("at F=" .. emu.framecount() .. "  tile9C: " .. hexfrom(0xC9C0, 32))
client.screenshot(OUT .. "/" .. TAG .. "_A.png")

for k = 0, 31 do memory.write_u8(0xC9C0 + k, 0xFF, "VRAM") end
say("poked 0xC9C0 .. 0xC9DF with FF")
emu.frameadvance()
say("at F=" .. emu.framecount() .. "  tile9C: " .. hexfrom(0xC9C0, 32))
client.screenshot(OUT .. "/" .. TAG .. "_B.png")

say("done")
log:close()