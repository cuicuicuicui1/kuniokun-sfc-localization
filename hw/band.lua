-- band.lua: drive from the user's battery save with a fixed input pattern and
-- screenshot every 8 frames.  Run it once on the clean original and once on the
-- build, then diff the two screenshot sets offline: any row the patch disturbs
-- shows up as a frame that differs from the original at the same index.
--
-- client.getpixel does not exist in this EmuHawk build, so the only reliable
-- detector is comparing pixels of the saved PNGs.
--
-- env: HW_TAG HW_SRAM HW_NF HW_EVERY
local TAG   = os.getenv('HW_TAG') or 'band'
local SRAM  = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v12.srm'
local NF    = tonumber(os.getenv('HW_NF') or '3000')
local EVERY = tonumber(os.getenv('HW_EVERY') or '8')
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
else
  line('NO SRAM ' .. SRAM)
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end

local dirs = { 'Right', 'Left', 'Down', 'Up' }
for f = 1, NF do
  local k = f % 300
  local pad = {}
  if k < 3 or (k >= 30 and k < 33) or (k >= 170 and k < 174) then
    pad = { A = true }
  elseif k == 60 then
    pad = { Start = true }
  elseif k == 160 then
    pad = { B = true }
  elseif k >= 180 and k < 240 then
    pad = { [dirs[math.floor(f / 300) % 4 + 1]] = true }
  end
  joypad.set(pad)
  emu.frameadvance()
  if f % EVERY == 0 then
    client.screenshot(string.format('%s_f%05d', TAG, f))
  end
end
line('done ' .. NF .. ' frames')
