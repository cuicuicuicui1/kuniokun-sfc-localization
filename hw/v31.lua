-- v31.lua: HUD name-widget probe (A/B original vs patched)
-- Every 60 frames count tilemap cells in $7800-$7FFF whose attribute high byte is $24
-- (that is how both the text drawer and the widget renderer tag their entries), and watch
-- the six exact VRAM words the engine's widget code writes to:
--   box tiles $78AA / $789B / $78BB (from tables at bank $01:$FC5D / $FC69)
--   name text $79C6 / $7A06 / $7A46 (cursors set in the routine at bank $01:$FC21+)
-- Logs only on change, one line per change:  F=<frame> attr24=<cells> <6 watch words>
local TAG = os.getenv("HW_TAG") or "v31"
local TO  = tonumber(os.getenv("HW_TO") or "3000")
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/" .. TAG .. ".log"
local f = io.open(OUT, "w")
f:write(string.format("# rom=%s hash=%s\n", gameinfo.getromname(), gameinfo.getromhash()))
f:flush()

local WATCH = {0x78AA, 0x789B, 0x78BB, 0x79C6, 0x7A06, 0x7A46}

local function scan()
  local n = 0
  for w = 0x7800, 0x7FFF do
    if memory.read_u8(2 * w + 1, "VRAM") == 0x24 then n = n + 1 end
  end
  return n
end

local function watch()
  local s = ""
  for i, w in ipairs(WATCH) do
    local lo = memory.read_u8(2 * w, "VRAM")
    local hi = memory.read_u8(2 * w + 1, "VRAM")
    s = s .. string.format(" %04X=%02X%02X", w, hi, lo)
  end
  return s
end

local function input(fc)
  if fc < 420 then
    if fc % 150 == 0 then joypad.set({Start = true}, 1) end
  else
    if fc % 30 == 0 then joypad.set({A = true}, 1) end
    if fc > 600 and fc % 37 == 0 then
      local keys = {"Up", "Down", "Left", "Right"}
      joypad.set({[keys[(math.floor(fc / 37) % 4) + 1]] = true}, 1)
    end
    if fc > 1500 and fc % 500 == 0 then joypad.set({Start = true}, 1) end
    if fc > 1500 and fc % 100 == 0 then joypad.set({B = true}, 1) end
  end
end

local last_n, last_w = nil, nil
local fc = emu.framecount()
while fc <= TO do
  input(fc)
  emu.frameadvance()
  fc = emu.framecount()
  if fc % 60 == 0 then
    local n = scan()
    local w = watch()
    if n ~= last_n or w ~= last_w then
      f:write(string.format("F=%d attr24cells=%d%s\n", fc, n, w))
      f:flush()
      last_n, last_w = n, w
    end
  end
end
f:write("done\n")
f:close()