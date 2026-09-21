-- v26.lua : measure the per-frame usage of the $0B00 VRAM upload queue.
-- $09DD = flush cursor, $09DF = append cursor.  The NMI flushes the queue and resets
-- both to 0 every frame, so the value of $09DF sampled at a frame boundary is exactly
-- how many bytes were queued during that frame.  The flusher masks the cursor to 8 bits
-- (and #$00ff), so the usable budget is 256 bytes per frame -- this run tells me how
-- much of it the game itself uses, i.e. my headroom for 32-byte glyph entries.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v26"
local TO = tonumber(os.getenv("HW_TO") or "1450")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end

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
  local dd, df = rd(0x09DD), rd(0x09DF)
  local dd2, df2 = rd(0x09DE), 0
  say(string.format("F=%d sdd=%02X sdf=%02X e8=%02X e9=%02X col=%02X 73=%02X",
    f, dd, df, rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x0373)))
end
log:close()