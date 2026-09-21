-- v28.lua : isolate the pixels a VRAM poke changes on screen.
--   Run this script twice with HW_POKE=0 and HW_POKE=1.  Both runs play the same
--   frame-indexed input sequence (the game is deterministic, checked earlier), so
--   the first screenshot of both runs is identical.  Run 0 stores A and C, one
--   frame apart with no poke.  Run 1 stores A and B, one frame apart, with the
--   VRAM tile used by the 5th column cell (tile 0x9C, VRAM byte 0xC9C0) filled
--   with FF right after A.  Then
--       A vs C  = what the game changes by itself in one frame
--       A vs B  = that plus the poke's effect
--   and the Python side subtracts the two to get exactly the poked cell.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v28"
local AT = tonumber(os.getenv("HW_AT") or "1398")
local POKE = (os.getenv("HW_POKE") or "0") == "1"
local PORTA = tonumber(os.getenv("HW_PORTA") or "0xC9C0")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

-- frame-indexed input: identical schedule in both runs, no dependence on a counter
local function feed(f)
  if f < 420 and (f % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (f % 30) == 0 then joypad.set({ A = true }, 1) end
  if f > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(f / 37) % 4) + 1]] = true }, 1)
  end
end

while emu.framecount() < AT do
  feed(emu.framecount() + 1)
  emu.frameadvance()
end
say(string.format("at F=%d poke=%s", emu.framecount(), tostring(POKE)))

local function hexfrom(a, n)
  local t = {}
  for k = 0, n - 1 do t[#t + 1] = string.format("%02X", memory.read_u8(a + k, "VRAM")) end
  return table.concat(t, " ")
end
say("tile9C before: " .. hexfrom(PORTA, 32))

client.screenshot(OUT .. "/" .. TAG .. "_A.png")
if POKE then
  for k = 0, 31 do memory.write_u8(PORTA + k, 0xFF, "VRAM") end
  say("poked " .. string.format("%04X", PORTA) .. " .. +31 with FF")
end

feed(emu.framecount() + 1)
emu.frameadvance()

local second = POKE and "B" or "C"
say("second shot at F=" .. emu.framecount() .. "  -> " .. second)
client.screenshot(OUT .. "/" .. TAG .. "_" .. second .. ".png")
say("done")
log:close()