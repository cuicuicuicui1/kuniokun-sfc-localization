-- forcebox.lua: drive into a dialogue scene, then put the game into the choice
-- prompt's state by hand and see whether the engine's own code draws the box.
--
-- $0392 is the prompt state and $F0F8 dispatches it through the table at
-- $03:F101 (JMP ($F101,X), X = $0392*2): 1 -> $F14E (draw one row per call,
-- $0395 = 0..2), 2 -> $F15F (timer), 3 -> $F17F (input).  $0363 picks the block
-- set ($F17D = [3, 8]) and $0374 bit 4 gates the state machine.
local TAG   = os.getenv('HW_TAG') or 'fbx'
local SRAM  = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v18.srm'
local AT    = tonumber(os.getenv('HW_AT') or '1400')
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end

memory.usememorydomain('WRAM')
local function dumpvram(name)
  local a = memory.read_bytes_as_array(0, 65536, 'VRAM')
  local f = assert(io.open(OUT .. name .. '.vram', 'wb'))
  local t = {}
  for i = 1, 65536 do t[i] = string.char(a[i]) end
  f:write(table.concat(t)); f:close()
end
local function dumpwram(name)
  local a = memory.read_bytes_as_array(0, 4096, 'WRAM')
  local f = assert(io.open(OUT .. name .. '.wram', 'wb'))
  local t = {}
  for i = 1, 4096 do t[i] = string.char(a[i]) end
  f:write(table.concat(t)); f:close()
end

local dirs = { 'Right', 'Left', 'Down', 'Up' }
for f = 1, AT do
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
end
dumpvram(TAG .. '_before'); dumpwram(TAG .. '_before')
line(string.format('before: 0363=%02X 0392=%02X 0395=%02X 0374=%02X 036E=%02X 036F=%02X 0391=%02X',
     memory.read_u8(0x0363, 'WRAM'), memory.read_u8(0x0392, 'WRAM'),
     memory.read_u8(0x0395, 'WRAM'), memory.read_u8(0x0374, 'WRAM'),
     memory.read_u8(0x036E, 'WRAM'), memory.read_u8(0x036F, 'WRAM'),
     memory.read_u8(0x0391, 'WRAM')))

-- put the prompt into "draw the rows" state
memory.write_u8(0x0363, 0, 'WRAM')                  -- yes/no block set
memory.write_u8(0x0392, 1, 'WRAM')                  -- state 1 = $F14E
memory.write_u8(0x0395, 0, 'WRAM')                  -- row 0
memory.write_u8(0x0374, memory.read_u8(0x0374, 'WRAM') | 0x10, 'WRAM')
memory.write_u8(0x0368, 0, 'WRAM')
for i = 1, 60 do emu.frameadvance() end
dumpvram(TAG .. '_after'); dumpwram(TAG .. '_after')
line(string.format('after : 0363=%02X 0392=%02X 0395=%02X 0374=%02X',
     memory.read_u8(0x0363, 'WRAM'), memory.read_u8(0x0392, 'WRAM'),
     memory.read_u8(0x0395, 'WRAM'), memory.read_u8(0x0374, 'WRAM')))
client.screenshot(TAG .. '_shot')
line('done')
client.exit()
