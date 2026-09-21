-- v15.lua : whole-timeline probe.  Logs every 30 frames from frame 0 so a ROM
-- that never reaches the dialogue still produces evidence.  "seen" counts
-- non-blank cells in the message tilemap (rows 0..3, top and bottom halves),
-- which is a programmatic stand-in for "how many glyphs are on screen".
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v15"
local TO = tonumber(os.getenv("HW_TO") or "1500")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end
local function tile_at(w)
  local lo = memory.read_u8(w * 2, "VRAM")
  local hi = memory.read_u8(w * 2 + 1, "VRAM")
  return (lo + (hi % 4) * 256)
end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
local idx = 0
local nextlog = 0
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
  if f >= nextlog then
    nextlog = f + 30
    local seen, first = 0, nil
    for r = 0, 3 do
      for c = 0, 27 do
        for h = 0, 1 do
          local v = tile_at(0x7C00 + r * 64 + 3 + c + h * 32)
          if v ~= 0 then
            seen = seen + 1
            if first == nil then first = string.format("%03X@%d/%d", v, r, c) end
          end
        end
      end
    end
    say(string.format("F=%d seen=%d first=%s e8=%02X e9=%02X col=%02X row=%02X 73=%02X 74=%02X",
      f, seen, tostring(first), rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x036E),
      rd(0x0373), rd(0x0374)))
  end
end
log:close()