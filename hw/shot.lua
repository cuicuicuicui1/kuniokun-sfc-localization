-- shot.lua : play N frames with scripted input, screenshot periodically, log dialog state
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "shot"
local MAXF = tonumber(os.getenv("HW_FRAMES") or "2400")

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local VR = "WRAM"
local function rd(a) return memory.read_u8(a, VR) end

say("tag=" .. TAG)
local idx = 0
while emu.framecount() < MAXF do
  idx = idx + 1
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  if (idx % 200) == 0 then
    say(string.format("f=%d 036D=%02X 036E=%02X 036F=%02X 03E8=%02X 03E9=%02X 09DF=%02X 0374=%02X 038C=%02X 038D=%02X",
      emu.framecount(), rd(0x036D), rd(0x036E), rd(0x036F), rd(0x03E8), rd(0x03E9), rd(0x09DF), rd(0x0374), rd(0x038C), rd(0x038D)))
    client.screenshot(string.format("%s/%s_f%05d.png", OUT, TAG, emu.framecount()))
  end
end
client.screenshot(OUT .. "/" .. TAG .. "_last.png")
local s = ""
for i = 0, 0x3F do
  s = s .. string.format("%02X ", rd(0x0B00 + i))
  if (i % 16) == 15 then say("scr " .. string.format("%04X", 0x0B00 + i - 15) .. ": " .. s); s = "" end
end
say("done")
log:close()