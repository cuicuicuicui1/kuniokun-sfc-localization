-- v33.lua : cleaner layout probe + post-frame VRAM readback.
-- Single 0xFF byte per tile at a position whose row differs between the two
-- candidate readings, so each cell answers "which row lit up" unambiguously.
-- The post-frame readback says whether the game re-uploaded the tile during
-- the frame (which would explain results that contradict the poke).
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v33"
local TO = tonumber(os.getenv("HW_TO") or "1400")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end
local function rd16(base)
  local s = ""
  for i = 0, 15 do s = s .. string.format("%02X", memory.read_u8(base + i, "VRAM") or -1) end
  return s
end

-- tile -> byte index that gets 0xFF (all other bytes 0)
--   byte 5  : rowint row2 (idx1 light) | planar row5 (idx1 light)
--   byte 12 : rowint row6 (idx2 dim)   | planar row4 (idx2 dim)
--   byte 2  : rowint row1 (idx1 light) | planar row2 (idx1 light)
--   byte 10 : rowint row5 (idx2 dim)   | planar row2 (idx2 dim)
--   byte 7  : rowint row3 (idx2 dim)   | planar row7 (idx1 light)
local TESTS = { { 0x9C, 5 }, { 0xE6, 12 }, { 0x04, 2 }, { 0x3E, 10 }, { 0x68, 7 } }

local idx = 0
while emu.framecount() < 1395 do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
  emu.frameadvance()
end
say(string.format("reached F=%d e8=%02X e9=%02X col=%02X 73=%02X", emu.framecount(),
  rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x0373)))

for _, t in ipairs(TESTS) do
  local tile, at = t[1], t[2]
  for i = 0, 15 do
    memory.write_u8(0xC000 + tile * 16 + i, (i == at) and 0xFF or 0x00, "VRAM")
  end
  say(string.format("poked tile %02X byte %d -> %s (partner %s)", tile, at,
    rd16(0xC000 + tile * 16), rd16(0xC000 + (tile + 1) * 16)))
end

emu.frameadvance()
say("after frame " .. tostring(emu.framecount()))
for _, t in ipairs(TESTS) do
  local tile = t[1]
  say(string.format("post tile %02X -> %s (partner %s)", tile,
    rd16(0xC000 + tile * 16), rd16(0xC000 + (tile + 1) * 16)))
end
client.screenshot(OUT .. "/" .. TAG .. "_P_f1396.png")
log:close()