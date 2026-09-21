-- hang.lua : run a ROM, press buttons, detect a stall by watching WRAM, dump state when stuck.
-- Usage: EmuHawk.exe --lua="path/to/hang.lua" "C:/path/without/spaces/rom.smc"
local OUT  = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG  = os.getenv("HW_TAG") or "run"
local MAXF = tonumber(os.getenv("HW_FRAMES") or "1800")

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

local VR = "WRAM"

local function rd(a) return memory.read_u8(a, VR) end
local function rdw(a) return rd(a) + rd(a + 1) * 256 end
local function hexdump(base, n, label)
  local parts = {}
  for i = 0, n - 1 do
    parts[#parts + 1] = string.format("%02X", rd(base + i))
    if (i % 16) == 15 then
      say(string.format("%s %04X: %s", label, base + i - 15, table.concat(parts, " ")))
      parts = {}
    end
  end
  if #parts > 0 then say(label .. " tail: " .. table.concat(parts, " ")) end
end

-- digest of the game's work RAM so we can tell when the CPU-side logic stops moving
local function digest()
  local h = 5381
  for a = 0x0000, 0x03FF do
    h = (h * 33 + rd(a)) % 4294967296
  end
  for a = 0x09D0, 0x09FF do
    h = (h * 33 + rd(a)) % 4294967296
  end
  for a = 0x0B00, 0x0BFF do
    h = (h * 33 + rd(a)) % 4294967296
  end
  return h
end

local function dumpstate(label)
  say(string.format("--- %s frame=%d digest=%d", label, emu.framecount(), digest()))
  say(string.format("  ptrs: 03E8=%02X 03E9=%02X 03EA=%02X 12=%02X 09DF=%02X 036D=%02X 036E=%02X 036F=%02X 0374=%02X 038C=%02X 03A9=%02X",
    rd(0x03E8), rd(0x03E9), rd(0x03EA), rd(0x12), rd(0x09DF), rd(0x036D), rd(0x036E), rd(0x036F), rd(0x0374), rd(0x038C), rd(0x03A9)))
  say(string.format("  dialog: 0362=%02X 0363=%02X 0371=%02X 0373=%02X 038A=%02X 038B=%02X 038D=%02X 038E=%02X 038F=%02X 0390=%02X 0392=%02X 0394=%02X",
    rd(0x0362), rd(0x0363), rd(0x0371), rd(0x0373), rd(0x038A), rd(0x038B), rd(0x038D), rd(0x038E), rd(0x038F), rd(0x0390), rd(0x0392), rd(0x0394)))
  say(string.format("  vars: 0011=%02X 1BA6=%02X 0359=%02X 035A=%02X 034A=%02X 034C=%02X 034E=%02X", rd(0x0011), rd(0x1BA6), rd(0x0359), rd(0x035A), rd(0x034A), rd(0x034C), rd(0x034E)))
  hexdump(0x03EA, 0x60, "  buf03EA")
  hexdump(0x0B00, 0x60, "  script0B")
  hexdump(0x0100, 0x40, "  stack")
end

say("start " .. tostring(emu.getsystemid()) .. " tag=" .. TAG)

local hist = {}
local lastd = -1
local same = 0
local stuck = false
local idx = 0

while emu.framecount() < MAXF do
  idx = idx + 1
  -- press A on a slow cycle (advance dialogs); Start occasionally (title screen)
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()

  local d = digest()
  if d == lastd then same = same + 1 else same = 0 end
  lastd = d
  hist[#hist + 1] = d
  if #hist > 8 then table.remove(hist, 1) end

  if (idx % 120) == 0 then
    say(string.format("t=%d frame=%d digest=%d 036E=%02X 036F=%02X 03E9=%02X 09DF=%02X 0374=%02X",
      idx, emu.framecount(), d, rd(0x036E), rd(0x036F), rd(0x03E9), rd(0x09DF), rd(0x0374)))
    client.screenshot(string.format("%s/%s_f%05d.png", OUT, TAG, emu.framecount()))
  end

  if same == 45 and not stuck then
    stuck = true
    say("=== STALL: WRAM unchanged for 45 frames at frame " .. emu.framecount() .. " ===")
    dumpstate("STALL")
    client.screenshot(OUT .. "/" .. TAG .. "_STALL.png")
    break
  end
  if same == 200 and stuck then break end
end

if not stuck then
  say("no stall detected within " .. MAXF .. " frames")
  dumpstate("END")
  client.screenshot(OUT .. "/" .. TAG .. "_END.png")
end
log:close()