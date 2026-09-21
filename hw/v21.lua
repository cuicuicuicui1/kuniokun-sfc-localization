-- v21.lua : does the game rewrite the font window?  Poke a distinctive pattern
-- into the VRAM bytes of one slot tile from the outside, then read it back on
-- later frames.  Survives -> nothing rewrites that area.  Reverted -> the game
-- re-uploads VRAM and any glyph the patch writes there will be wiped.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v21"
local TO = tonumber(os.getenv("HW_TO") or "1510")
local POKE_AT = tonumber(os.getenv("HW_POKE") or "1395")
local AMP = os.getenv("HW_USEDOMAIN") == "1"

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

-- byte address of word 0x6020 (tile $04, the 'bao' slot tile)
local W = 0x6020
local BYTE = W * 2
local PAT = {}
for k = 0, 31 do PAT[k] = 0x30 + k end

local function read_domain()
  local t = {}
  for k = 0, 31 do t[#t + 1] = memory.read_u8(BYTE + k, "VRAM") end
  return t
end
local function write_domain()
  for k = 0, 31 do memory.write_u8(BYTE + k, PAT[k], "VRAM") end
end
local function checksum(t)
  local s = 0
  for k = 0, 31 do s = s + t[k] end
  return s
end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()) .. " poke=" .. POKE_AT)
local idx = 0
local marks = { [POKE_AT] = "poke", [POKE_AT + 1] = "after", [POKE_AT + 2] = "after",
  [POKE_AT + 5] = "after", [POKE_AT + 15] = "after", [POKE_AT + 55] = "after",
  [1500] = "after", [1505] = "after" }
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
  if marks[f] == "poke" then
    local before = read_domain()
    write_domain()
    local now = read_domain()
    say(string.format("F=%d before sum=%d  after-write sum=%d  equal-pattern=%s",
      f, checksum(before), checksum(now), tostring(now[1] == PAT[1] and now[31] == PAT[31])))
  elseif marks[f] == "after" then
    local now = read_domain()
    local n = 0
    for k = 0, 31 do
      if now[k] == PAT[k] then n = n + 1 end
    end
    say(string.format("F=%d kept %d/32 bytes  first=%02X last=%02X", f, n, now[1], now[31]))
  end
end