-- rep4: clean perturbation run.  The state saved at the strip frame is reloaded
-- before every perturbation, so the scene cannot drift; the pad is cleared.
-- env: HW_TAG HW_SRAM HW_F
local TAG  = os.getenv('HW_TAG') or 'rep4'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v12.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local FF   = tonumber(os.getenv('HW_F') or '2590')
local STATE = OUT .. (os.getenv('HW_STATE') or 'rep3_strip.state')
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
local dirs = { 'Right', 'Left', 'Down', 'Up' }
local function drive()
  local f = emu.framecount() - 119
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
joypad.set({})
line('reached ' .. emu.framecount())
local ok = pcall(function() savestate.save(STATE) end)
line('state saved ' .. tostring(ok))

local function pert(name, dom, off, n, fill)
  local ok2 = pcall(function() savestate.load(STATE) end)
  if not ok2 then line('load failed ' .. name); return end
  for a = 0, n - 1 do memory.write_u8(off + a, fill or 0, dom) end
  joypad.set({})
  emu.frameadvance()
  client.screenshot(TAG .. '_' .. name)
  line('pert ' .. name)
end

pert('control', 'VRAM', 0, 0)          -- state reload only
pert('cgram', 'CGRAM', 0, 512)
pert('oam', 'OAM', 0, 544)
for i = 0, 31 do
  pert(string.format('map_%04X', i * 0x800), 'VRAM', i * 0x800, 0x800)
end
for i = 0, 15 do
  pert(string.format('tile_%04X', i * 0x1000), 'VRAM', i * 0x1000, 0x1000, 0x55)
end
line('done')