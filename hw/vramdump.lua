-- vramdump.lua: same drive pattern as band.lua, but instead of screenshots it
-- writes the 64 KB VRAM (and the low WRAM page that holds the prompt's state
-- variables) every HW_EVERY frames.  Used to catch the yes/no choice box on
-- screen and read back which tiles it actually drew.
--
-- env: HW_TAG HW_SRAM HW_NF HW_EVERY
local TAG   = os.getenv('HW_TAG') or 'vrd'
local SRAM  = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v18.srm'
local NF    = tonumber(os.getenv('HW_NF') or '3000')
local EVERY = tonumber(os.getenv('HW_EVERY') or '10')
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

memory.usememorydomain('VRAM')
local function dumpvram(tag)
  local a = memory.read_bytes_as_array(0, 65536, 'VRAM')
  local f = assert(io.open(string.format('%s%s_%05d.vram', OUT, tag, emu.framecount()), 'wb'))
  local t = {}
  for i = 1, 65536 do t[i] = string.char(a[i]) end
  f:write(table.concat(t)); f:close()
end
memory.usememorydomain('WRAM')
local function dumpwram(tag)
  local a = memory.read_bytes_as_array(0, 4096, 'WRAM')
  local f = assert(io.open(string.format('%s%s_%05d.wram', OUT, tag, emu.framecount()), 'wb'))
  local t = {}
  for i = 1, 4096 do t[i] = string.char(a[i]) end
  f:write(table.concat(t)); f:close()
end

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
    dumpvram(TAG); dumpwram(TAG)
  end
end
line('done ' .. NF .. ' frames')
client.exit()
