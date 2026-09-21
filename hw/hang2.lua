-- hang2.lua : long gameplay session, wander + advance dialogs, detect a real stall and dump state
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "long"
local MAXF = tonumber(os.getenv("HW_FRAMES") or "8000")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local VR = "WRAM"
local function rd(a) return memory.read_u8(a, VR) end
local function digest()
  local h = 5381
  for a = 0x0000, 0x07FF do h = (h * 33 + rd(a)) % 4294967296 end
  for a = 0x0B00, 0x0BFF do h = (h * 33 + rd(a)) % 4294967296 end
  return h
end
local function dumpstate(label)
  say(string.format("--- %s frame=%d", label, emu.framecount()))
  say(string.format("  036D=%02X 036E=%02X 036F=%02X 0371=%02X 0373=%02X 0374=%02X 038A=%02X 038B=%02X 038C=%02X 038D=%02X 038E=%02X 038F=%02X 0390=%02X 0392=%02X 0394=%02X",
    rd(0x036D), rd(0x036E), rd(0x036F), rd(0x0371), rd(0x0373), rd(0x0374), rd(0x038A), rd(0x038B), rd(0x038C), rd(0x038D), rd(0x038E), rd(0x038F), rd(0x0390), rd(0x0392), rd(0x0394)))
  say(string.format("  0011=%02X 03E8=%02X 03E9=%02X 12=%02X 09DF=%02X 0359=%02X 1BA6=%02X 1BA7=%02X",
    rd(0x0011), rd(0x03E8), rd(0x03E9), rd(0x12), rd(0x09DF), rd(0x0359), rd(0x1BA6), rd(0x1BA7)))
  local t = {}
  for i = 0, 0x3F do t[#t + 1] = string.format("%02X", rd(0x03EA + i)) end
  say("  msg 03EA: " .. table.concat(t, " "))
  t = {}
  for i = 0, 0x5F do t[#t + 1] = string.format("%02X", rd(0x0B00 + i)) end
  say("  scr 0B00: " .. table.concat(t, " "))
  t = {}
  for i = 0, 0x1F do t[#t + 1] = string.format("%02X", rd(0x0B80 + i)) end
  say("  scr 0B80: " .. table.concat(t, " "))
  t = {}
  for i = 0x0100, 0x01FF do t[#t + 1] = string.format("%02X", rd(i)) end
  say("  stack: " .. table.concat(t, " "))
end

say("tag=" .. TAG)
local idx, same, lastd = 0, 0, -1
local dirs = { "Right", "Down", "Left", "Up" }
local stuck = false
while emu.framecount() < MAXF do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 500 then
    local d = dirs[(math.floor(idx / 37) % 4) + 1]
    joypad.set({ [d] = true }, 1)
  end
  emu.frameadvance()
  local d = digest()
  if d == lastd then same = same + 1 else same = 0 end
  lastd = d
  if (idx % 400) == 0 then
    say(string.format("f=%d 0374=%02X 036E=%02X 036F=%02X 03E8=%02X 03E9=%02X 09DF=%02X",
      emu.framecount(), rd(0x0374), rd(0x036E), rd(0x036F), rd(0x03E8), rd(0x03E9), rd(0x09DF)))
    client.screenshot(string.format("%s/%s_f%05d.png", OUT, TAG, emu.framecount()))
  end
  if same == 50 and not stuck then
    stuck = true
    say("=== STALL at frame " .. emu.framecount() .. " ===")
    dumpstate("STALL")
    client.screenshot(OUT .. "/" .. TAG .. "_STALL.png")
    break
  end
end
if not stuck then
  say("no stall in " .. MAXF .. " frames")
  dumpstate("END")
end
client.screenshot(OUT .. "/" .. TAG .. "_last.png")
log:close()