-- v23.lua : does the game rewrite the font window at VRAM $6000-$67FF?
--
-- Lua writes go straight into the core's VRAM array, bypassing $2116/$2118, so if
-- a pattern poked from here disappears within a frame or two, the game itself
-- re-uploads (or clears) that window -- which would explain why the patched
-- drawer's own CPU writes to $2118 are never observable.
--
-- Pattern A: tile 0x9C (byte 0xC9C0..0xC9DF) -- a font-window tile my slots use.
-- Pattern B: byte 0x1000 (word 0x0800)        -- control, a likely unused area.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v23"
local TO = tonumber(os.getenv("HW_TO") or "1700")
local POKE = tonumber(os.getenv("HW_POKE") or "1395")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
memory.usememorydomain("VRAM")

local function hex(addr, n)
  local t = {}
  for k = 0, n - 1 do
    local b = memory.read_u8(addr + k)
    t[#t + 1] = string.format("%02X", b or 255)
  end
  return table.concat(t, " ")
end

local function poke(addr, n, base)
  for k = 0, n - 1 do memory.write_u8(addr + k, (base + k) % 256) end
end

local A_ADDR, B_ADDR = 0xC9C0, 0x1000
local REPORT = { 0, 1, 2, 3, 5, 10, 30, 90, 200, 400 }
local poked = false
local idx = 0
local nextrep = 1

while emu.framecount() < TO do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()

  local f = emu.framecount()
  if (not poked) and f >= POKE then
    poked = true
    poke(A_ADDR, 32, 0x40)
    poke(B_ADDR, 32, 0x80)
    say(string.format("F=%d poke: A(0xC9C0)=%s", f, hex(A_ADDR, 32)))
    say(string.format("F=%d poke: B(0x1000)=%s", f, hex(B_ADDR, 8)))
  end
  if poked and nextrep <= #REPORT and f >= POKE + REPORT[nextrep] then
    say(string.format("  +%-3df F=%d A=%s | B=%s",
      REPORT[nextrep], f, hex(A_ADDR, 16), hex(B_ADDR, 8)))
    nextrep = nextrep + 1
  end
end
say("done")