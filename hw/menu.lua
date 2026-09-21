-- menu.lua: burn the intro dialogue, then open the pause menu and photograph it.
-- Run on the clean original and on the build; the two screenshot sets show
-- whether the command window's labels come out as hanzi and whether anything
-- else in the window changed.
-- env: HW_TAG HW_SRAM HW_BOOT HW_BURN
local TAG  = os.getenv('HW_TAG') or 'menu'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kuniokun_ORIGINAL.srm'
local BOOT = tonumber(os.getenv('HW_BOOT') or '400')
local BURN = tonumber(os.getenv('HW_BURN') or '300')
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function w(a) return memory.read_u8(a, 'WRAM') end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
end
client.reboot_core()
for _ = 1, BOOT do emu.frameadvance() end
local function tap(pad, hold, gap)
  joypad.set(pad)
  for _ = 1, (hold or 2) do emu.frameadvance() end
  joypad.set({})
  for _ = 1, (gap or 10) do emu.frameadvance() end
end
for _ = 1, BURN do tap({ A = true }, 2, 10) end
line('dialogue burned')

-- open the menu and keep shooting while it draws
joypad.set({ Start = true })
emu.frameadvance()
joypad.set({})
for i = 1, 40 do
  emu.frameadvance()
  if i % 4 == 0 then
    client.screenshot(string.format('%s_open%02d', TAG, i))
    line(string.format('open%02d DE1=%02X 036E=%02X 0374=%02X 0391=%02X 0BFB=%02X',
      i, w(0x0DE1), w(0x036E), w(0x0374), w(0x0391), w(0x0BFB)))
  end
end
-- walk the cursor and shoot each position
for i = 1, 5 do
  tap({ Right = true }, 2, 20)
  client.screenshot(string.format('%s_right%d', TAG, i))
end
for i = 1, 5 do
  tap({ Down = true }, 2, 20)
  client.screenshot(string.format('%s_down%d', TAG, i))
end
tap({ B = true }, 2, 40)
client.screenshot(TAG .. '_closed')
line('done')
