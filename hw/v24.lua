-- v24.lua : font-window wipe test.
-- Pokes a marker pattern into VRAM bytes 0xC9C0..0xC9DF (font tiles 0x9C/0x9D, the
-- slot used by the first CJK char of the 1382-frame message) at chosen frames, then
-- samples every frame and classifies the content as:
--   P      = my marker pattern
--   O      = original Japanese font bytes from ROM 0x0F8000+0x9C*16
--   C:<ch> = my glyph pool bytes for one of the five known chars (drawer's write landed!)
--   ?      = anything else (prints first 8 bytes)
-- Answers two questions at once: does the game rewrite the font window while a message
-- is drawn, and does my drawer's VRAM write ever reach the PPU.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v24"
local ROMF = os.getenv("HW_ROM") or "C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kfix.smc"
local TO = tonumber(os.getenv("HW_TO") or "1440")
local BASE = 0xC9C0
local N = 32
local POKES = {}
for w in tostring(os.getenv("HW_POKE") or "1384,1386,1388"):gmatch("[^,]+") do POKES[tonumber(w)] = true end

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end
local function hex(t, n) local s = ""; for i = 0, (n or 8) - 1 do s = s .. string.format("%02X", t[i] % 256) end; return s end

local function read_rom(off, n)
  local fh = io.open(ROMF, "rb")
  if not fh then return nil end
  fh:seek("set", off)
  local s = fh:read(n)
  fh:close()
  if not s or #s ~= n then return nil end
  local t = {}
  for i = 1, n do t[i - 1] = string.byte(s, i) end
  return t
end

local orig = read_rom(0x0F8000 + 0x9C * 16, N)
local pools = {}
for _, e in ipairs({
  { "猪", 0x1387E0 }, { "肉", 0x148920 }, { "包", 0x110020 },
  { "一", 0x1082A0 }, { "个", 0x108520 },
}) do
  local t = read_rom(e[2], N)
  if t then pools[#pools + 1] = { e[1], t } end
end

local pat = {}
for i = 0, N - 1 do pat[i] = 0x80 + i end

local function read32()
  local t = {}
  for i = 0, N - 1 do t[i] = memory.read_u8(BASE + i, "VRAM") or -1 end
  return t
end
local function cmp(t, u)
  if not u then return false end
  for i = 0, N - 1 do if t[i] ~= u[i] then return false end end
  return true
end
local function classify(t)
  if cmp(t, pat) then return "P" end
  if cmp(t, orig) then return "O" end
  for _, p in ipairs(pools) do if cmp(t, p[2]) then return "C:" .. p[1] end end
  return "?:" .. hex(t, 8)
end
local function poke()
  for i = 0, N - 1 do memory.write_u8(BASE + i, pat[i], "VRAM") end
end

say(string.format("tag=%s rom=%s oriok=%s pools=%d pokes=%s", TAG, tostring(gameinfo.getromname()),
  tostring(orig ~= nil), #pools, tostring(os.getenv("HW_POKE"))))

local idx = 0
local prev = ""
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
  if POKES[f] then
    poke()
    say(string.format("F=%d POKE-marker", f))
  end
  if f >= 1378 then
    local c = classify(read32())
    if c ~= prev then
      say(string.format("F=%d tile9C=%-10s e8=%02X e9=%02X col=%02X row=%02X 73=%02X 74=%02X",
        f, c, rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x036E), rd(0x0373), rd(0x0374)))
      prev = c
    end
  end
end
poke()
say("F=" .. tostring(emu.framecount()) .. " POKE(post-text)")
for i = 1, 40 do
  emu.frameadvance()
  if i % 5 == 0 then say(string.format("F=%d tile9C=%s", emu.framecount(), classify(read32()))) end
end
log:close()