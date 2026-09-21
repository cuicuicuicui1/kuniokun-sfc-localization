-- resume.lua: load a battery save and photograph what the game does with it.
-- No input for the first stretch, then a few A presses, shooting all the way.
-- env: HW_TAG HW_SRAM HW_NF
local TAG  = os.getenv('HW_TAG') or 'resume'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v15.srm'
local NF   = tonumber(os.getenv('HW_NF') or '2400')
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function w(a) return memory.read_u8(a, 'WRAM') end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d .. ' from ' .. SRAM)
end
client.reboot_core()
for f = 1, NF do
  local pad = {}
  if f == 400 or f == 460 then pad = { Start = true } end
  if f > 500 and (f % 240) < 3 then pad = { A = true } end
  joypad.set(pad)
  emu.frameadvance()
  if f % 60 == 0 then
    client.screenshot(string.format('%s_f%05d', TAG, f))
    line(string.format('f%05d 6E=%02X 6F=%02X 91=%02X 74=%02X 0DE1=%02X 0DE3=%02X 1BA6=%02X',
      f, w(0x036E), w(0x036F), w(0x0391), w(0x0374), w(0x0DE1), w(0x0DE3), w(0x1BA6)))
  end
end
line('done')
