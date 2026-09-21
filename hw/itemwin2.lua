-- itemwin2: reach gameplay, open the pause menu, choose "どうぐをつかう", and
-- watch the three tile map cells the item window draws into.
--
-- The pause menu's own cell table is $03:F743: row 0 holds きりょくをつかう
-- (cells 1..7) and どうぐをつかう (cells 12..19).  So: Start, Right, A should
-- pick the item command.
--
-- env: HW_TAG HW_SRAM HW_BOOT
local TAG  = os.getenv('HW_TAG') or 'itemwin2'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kuniokun_ORIGINAL.srm'
local BOOT = tonumber(os.getenv('HW_BOOT') or '600')
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

local CELLS = { 0xF38C, 0xF40C, 0xF48C }          -- $79C6 / $7A06 / $7A46
local function cells()
  local t = {}
  for _, c in ipairs(CELLS) do
    local s = {}
    for i = 0, 5 do s[#s + 1] = string.format('%02X', vw(c + i)) end
    t[#t + 1] = table.concat(s, '')
  end
  return table.concat(t, ' ')
end

local last = nil
local function snap(label)
  local c = cells()
  local mark = (last and c ~= last) and '  <== CHANGED' or ''
  last = c
  line(string.format('%-16s DE1=%02X DE3=%02X DE5=%02X DE7=%02X 1BA6=%02X 1B5A=%02X 1B5B=%02X 0374=%02X 036E=%02X 0391=%02X  E5..ED=%02X%02X%02X%02X%02X%02X%02X%02X%02X  cells %s%s',
    label, w(0x0DE1), w(0x0DE3), w(0x0DE5), w(0x0DE7), w(0x1BA6), w(0x1B5A), w(0x1B5B),
    w(0x0374), w(0x036E), w(0x0391),
    w(0x01E5), w(0x01E6), w(0x01E7), w(0x01E8), w(0x01E9),
    w(0x01EA), w(0x01EB), w(0x01EC), w(0x01ED), c, mark))
  client.screenshot(TAG .. '_' .. label)
end

local function tap(pad, hold, gap)
  joypad.set(pad)
  for _ = 1, (hold or 3) do emu.frameadvance() end
  joypad.set({})
  for _ = 1, (gap or 40) do emu.frameadvance() end
end

snap('boot')
-- get through the title / intro
tap({ Start = true }, 3, 60); snap('a_start')
tap({ A = true }, 3, 60);     snap('a_A')
tap({ A = true }, 3, 60);     snap('a_A2')
tap({ A = true }, 3, 120);    snap('a_A3')
for i = 1, 6 do
  tap({ A = true }, 3, 60)
  tap({ B = true }, 3, 20)
end
snap('a_after')

-- now the pause menu, a few times, walking the cursor
for r = 1, 3 do
  tap({ Start = true }, 3, 60);      snap(string.format('r%d_start', r))
  tap({ Right = true }, 3, 30);      snap(string.format('r%d_right', r))
  tap({ A = true }, 3, 90);          snap(string.format('r%d_A', r))
  tap({ Down = true }, 3, 30);       snap(string.format('r%d_down', r))
  tap({ A = true }, 3, 90);          snap(string.format('r%d_A2', r))
  tap({ B = true }, 3, 30);          snap(string.format('r%d_B', r))
  tap({ B = true }, 3, 60);          snap(string.format('r%d_B2', r))
end
line('done')
