-- titlemenu.lua: what does the title screen offer, and can we load the save?
-- env: HW_TAG HW_SRAM HW_BOOT
local TAG  = os.getenv('HW_TAG') or 'titlemenu'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kuniokun_ORIGINAL.srm'
local BOOT = tonumber(os.getenv('HW_BOOT') or '300')
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
end
client.reboot_core()
for _ = 1, BOOT do emu.frameadvance() end
local function shot(n) client.screenshot(string.format('%s_%s', TAG, n)) end
local function tap(pad, hold, gap)
  joypad.set(pad)
  for _ = 1, (hold or 2) do emu.frameadvance() end
  joypad.set({})
  for _ = 1, (gap or 12) do emu.frameadvance() end
end
shot('t000')
for i = 1, 10 do
  tap({ Start = true }, 2, 20)
  shot(string.format('start%02d', i))
end
for i = 1, 6 do
  tap({ Down = true }, 2, 20)
  shot(string.format('down%02d', i))
end
for i = 1, 4 do
  tap({ A = true }, 2, 30)
  shot(string.format('A%02d', i))
end
-- let it run a while and photograph
for i = 1, 12 do
  for _ = 1, 60 do emu.frameadvance() end
  shot(string.format('run%02d', i))
end
line('done')
