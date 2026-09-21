-- v22.lua : what is the VRAM memory domain really?  Prints the domain list, the
-- domain size, and reads at several addresses so the byte/word scaling used by
-- every earlier probe can be confirmed or corrected.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v22"
local TO = tonumber(os.getenv("HW_TO") or "1410")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
say("domains: " .. table.concat(memory.getmemorydomainlist(), ","))
local ok, size = pcall(memory.getmemorydomainsize, "VRAM")
say("VRAM size: " .. tostring(ok) .. " " .. tostring(size))
ok, size = pcall(memory.getmemorydomainsize, "CARTROM")
say("CARTROM size: " .. tostring(ok) .. " " .. tostring(size))

local idx = 0
local done = false
while emu.framecount() < TO do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()
  if emu.framecount() == 1400 and not done then
    done = true
    for _, a in ipairs({ 0x0, 0x1000, 0x7800, 0x7C00, 0xC000, 0xC040, 0xC05F,
      0xD03F, 0xE000, 0xFFF0, 0xFFFE, 0xFFFF, 0x10000, 0x18000 }) do
      local b = memory.read_u8(a, "VRAM")
      local w = memory.read_u16_le(a, "VRAM")
      say(string.format("addr %06X  u8=%s  u16=%s", a, tostring(b), tostring(w)))
    end
    -- is the domain writable?
    local before = memory.read_u8(0xC040, "VRAM")
    local wok = pcall(memory.write_u8, 0xC040, 0x5A, "VRAM")
    local after = memory.read_u8(0xC040, "VRAM")
    say(string.format("write test: ok=%s before=%s after=%s", tostring(wok),
      tostring(before), tostring(after)))
    local wok2 = pcall(memory.usememorydomain, "VRAM")
    say("usememorydomain ok=" .. tostring(wok2))
  end
end