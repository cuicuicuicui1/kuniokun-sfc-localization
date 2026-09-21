-- rep3: run to the frame where the strip is on screen, then perturb one region
-- of VRAM/CGRAM/OAM at a time and screenshot, so the owner of the strip's
-- pixels can be read off the differences.
-- env: HW_TAG HW_SRAM HW_F (frame with the strip, default 2590)
local TAG  = os.getenv('HW_TAG') or 'rep3'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v12.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local FF   = tonumber(os.getenv('HW_F') or '2590')
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function wb(a, v) memory.write_u8(a, v, 'VRAM') end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end

local dirs = { 'Right', 'Left', 'Down', 'Up' }
local function drive()
  local f = emu.framecount() - 119      -- same phase as rep1/rep2
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
end
for f = 1, FF do drive(); emu.frameadvance() end
line('reached ' .. emu.framecount())
local ok = pcall(function() savestate.save(OUT .. TAG .. '_strip.state') end)
line('state saved ' .. tostring(ok))
client.screenshot(TAG .. '_base')

local function grab(dom, n)
  local t = {}
  for a = 0, n - 1 do t[a + 1] = string.char(memory.read_u8(a, dom)) end
  return t
end
local function put(dom, t)
  for a = 1, #t do memory.write_u8(a - 1, t:byte(a), dom) end
end

local function pert(name, dom, off, n)
  local old = grab(dom, n)
  local z = string.rep('\0', n)
  -- offset the zero run
  for a = 0, n - 1 do memory.write_u8(off + a, 0, dom) end
  emu.frameadvance()
  client.screenshot(TAG .. '_' .. name)
  put(dom, z)  -- no-op keeps the string referenced
  for a = 0, n - 1 do memory.write_u8(off + a, old[a + 1]:byte(1), dom) end
  emu.frameadvance()
  line('pert ' .. name)
end

pert('cgram', 'CGRAM', 0, 512)
pert('oam', 'OAM', 0, 544)
for i = 0, 31 do
  pert(string.format('map_%04X', i * 0x800), 'VRAM', i * 0x800, 0x800)
end
for i = 0, 15 do
  pert(string.format('tile_%04X', i * 0x1000), 'VRAM', i * 0x1000, 0x1000)
end
-- targeted: the two map rows the diff flagged
pert('map0000_r24', 'VRAM', 0x0600, 0x40)
pert('map7C00_r10', 'VRAM', 0xFA80, 0x80)
pert('map7C00_r19', 'VRAM', 0xFC80, 0x40)
line('done')