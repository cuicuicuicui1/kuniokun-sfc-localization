-- itemwin3: burn the intro dialogue with A, then open the pause menu and pick
-- "どうぐをつかう", watching the three tile map cells the item window draws to.
-- env: HW_TAG HW_SRAM HW_BOOT HW_BURN
local TAG  = os.getenv('HW_TAG') or 'itemwin3'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kuniokun_ORIGINAL.srm'
local BOOT = tonumber(os.getenv('HW_BOOT') or '400')
local BURN = tonumber(os.getenv('HW_BURN') or '260')
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vw(a) return memory.read_u8(a, 'VRAM') end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
end
client.reboot_core()
for _ = 1, BOOT do emu.frameadvance() end

local CELLS = { 0xF38C, 0xF40C, 0xF48C }
local function cells()
  local t = {}
  for _, c in ipairs(CELLS) do
    local s = {}
    for i = 0, 5 do s[#s + 1] = string.format('%02X', vw(c + i)) end
    t[#t + 1] = table.concat(s, '')
  end
  return table.concat(t, ' ')
end
-- the pause menu's label cells, from the engine's table at $03:F743
local function boxmap()
  local s = {}
  for i = 0, 51 do s[#s + 1] = string.format('%02X', vw(0xF800 + i)) end
  return table.concat(s)
end
local last, lastbox = nil, nil
local function snap(label)
  local c, b = cells(), boxmap()
  local mark = (last and c ~= last) and '  <== CELLS CHANGED' or ''
  if lastbox and b ~= lastbox then mark = mark .. '  <== BOXMAP CHANGED' end
  last, lastbox = c, b
  line(string.format('%-14s DE1=%02X DE3=%02X DE5=%02X DE7=%02X 1BA6=%02X 1B5A=%02X 1B5B=%02X 0374=%02X  E5..ED=%02X%02X%02X%02X%02X%02X%02X%02X%02X  cells %s%s',
    label, w(0x0DE1), w(0x0DE3), w(0x0DE5), w(0x0DE7), w(0x1BA6), w(0x1B5A), w(0x1B5B), w(0x0374),
    w(0x01E5), w(0x01E6), w(0x01E7), w(0x01E8), w(0x01E9),
    w(0x01EA), w(0x01EB), w(0x01EC), w(0x01ED), c, mark))
  client.screenshot(TAG .. '_' .. label)
end
local function tap(pad, hold, gap)
  joypad.set(pad)
  for _ = 1, (hold or 2) do emu.frameadvance() end
  joypad.set({})
  for _ = 1, (gap or 10) do emu.frameadvance() end
end

snap('boot')
line('burning %d A presses' % BURN)
for i = 1, BURN do
  tap({ A = true }, 2, 10)
  if i % 40 == 0 then snap(string.format('burn%03d', i)) end
end
snap('after_burn')

for r = 1, 4 do
  tap({ Start = true }, 3, 40);  snap(string.format('r%d_start', r))
  tap({ Right = true }, 3, 20);  snap(string.format('r%d_right', r))
  tap({ A = true }, 3, 60);      snap(string.format('r%d_A', r))
  tap({ Down = true }, 3, 20);   snap(string.format('r%d_down', r))
  tap({ A = true }, 3, 60);      snap(string.format('r%d_A2', r))
  tap({ B = true }, 3, 20);      snap(string.format('r%d_B', r))
  tap({ B = true }, 3, 40);      snap(string.format('r%d_B2', r))
  tap({ A = true }, 2, 10)
  tap({ A = true }, 2, 10)
end
line('done')
