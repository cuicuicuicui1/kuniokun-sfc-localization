-- v30.lua : long scripted run that watches for widget activity.
--   (a) any tilemap cell (VRAM $7800-$7FFF) whose attribute byte is $24 and whose
--       tile number belongs to my slot table, but which is NOT one of the dialog
--       grid cells -> that would be a widget drawn through my dispatcher;
--   (b) the three widget boxes the engine draws at $78AA/$789B/$78BB with direct
--       VRAM writes: do they ever show up?  That tells whether such direct writes
--       land at all in the widget's calling context.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v30"
local TO = tonumber(os.getenv("HW_TO") or "3000")
local CNROM = os.getenv("HW_ROM") or "C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local SLOTS = {}
do
  local f = assert(io.open(CNROM, "rb"))
  f:seek("set", 0x1E900)
  local raw = f:read(114)
  f:close()
  for i = 0, 113 do
    local t = string.byte(raw, i + 1)
    if not t or t == 0 then break end
    SLOTS[t] = i
    SLOTS[t + 1] = i
  end
end

-- the dialog grid cells: $7C03 + row*$40 + col, two tilemap rows each
local DIALOG = {}
for row = 0, 15 do
  for col = 0, 25 do
    DIALOG[0x7C00 + row * 0x40 + 3 + col] = true
  end
end

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function r8(a) return memory.read_u8(a, "VRAM") end
local function word(w) return r8(w * 2) + r8(w * 2 + 1) * 256 end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
local seen = {}
local boxed = false
local idx = 0
while emu.framecount() < TO do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
  if idx > 1500 and (idx % 500) == 0 then joypad.set({ Start = true }, 1) end
  if idx > 1500 and (idx % 100) == 0 then joypad.set({ B = true }, 1) end
  emu.frameadvance()
  local f = emu.framecount()

  if (f % 60) == 0 then
    local msg = {}
    for w = 0x7800, 0x7FFF do
      local lo, hi = r8(w * 2), r8(w * 2 + 1)
      if hi == 0x24 and SLOTS[lo] and not DIALOG[w] and not seen[w] then
        seen[w] = true
        msg[#msg + 1] = string.format("cell %04X tile %02X slot %02X", w, lo, SLOTS[lo])
      end
    end
    if #msg > 0 then say(string.format("F=%d widget-ish cells: %s", f, table.concat(msg, " | "))) end
    if not boxed then
      for _, w in ipairs({ 0x78AA, 0x789B, 0x78BB }) do
        local v = word(w)
        if (v >> 8) == 0x24 then
          boxed = true
          say(string.format("F=%d widget box appeared at %04X: %s", f, w,
            string.format("%04X %04X %04X %04X", word(w), word(w + 1), word(w + 2), word(w + 3))))
        end
      end
    end
  end
  if (f % 300) == 0 then
    say(string.format("F=%d state 0041..48=%02X %02X %02X %02X %02X %02X %02X %02X  1BA6=%02X 01EB..=%02X %02X %02X",
      f, r8(0x0041) and memory.read_u8(0x0041, "WRAM") or 0,
      memory.read_u8(0x0042, "WRAM"), memory.read_u8(0x0043, "WRAM"), memory.read_u8(0x0044, "WRAM"),
      memory.read_u8(0x0045, "WRAM"), memory.read_u8(0x0046, "WRAM"), memory.read_u8(0x0047, "WRAM"),
      memory.read_u8(0x0048, "WRAM"), memory.read_u8(0x1BA6, "WRAM"),
      memory.read_u8(0x01EB, "WRAM"), memory.read_u8(0x01EC, "WRAM"), memory.read_u8(0x01ED, "WRAM")))
  end
end
say("done, widget-ish cells seen: " .. tostring(#seen))
log:close()