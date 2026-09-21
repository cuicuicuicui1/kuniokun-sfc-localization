-- rep1: drive from the user's battery save, hunt the coloured strip, and dump
-- the whole machine state the moment it is on screen.
--   * detector: near-(0,198,0) pixels in the field band (y=96..174); the room
--     scenes are brown/orange there, so a run of green means the strip.
--   * every 8 frames a screenshot, so the look of a hit can be checked later.
-- env: HW_TAG HW_SRAM HW_NF
local TAG  = os.getenv('HW_TAG') or 'rep1'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v12.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local NF   = tonumber(os.getenv('HW_NF') or '9000')
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
  line('sram written ' .. #d)
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end

local fmt = {}
for _, xy in ipairs({ { 128, 60 }, { 128, 151 }, { 128, 160 }, { 128, 220 }, { 8, 8 } }) do
  local ok, c = pcall(function() return client.getpixel(xy[1], xy[2]) end)
  fmt[#fmt + 1] = xy[1] .. ',' .. xy[2] .. '=' .. tostring(ok) .. ':' .. tostring(c)
end
line('pixels ' .. table.concat(fmt, '  '))

local function dump(tag)
  local g = assert(io.open(OUT .. TAG .. '_' .. tag .. '_vram.bin', 'wb'))
  for a = 0, 65535 do g:write(string.char(vb(a))) end
  g:close()
  local h = assert(io.open(OUT .. TAG .. '_' .. tag .. '_wram.bin', 'wb'))
  for a = 0, 0x1FFF do h:write(string.char(w(a))) end
  h:close()
  local c = assert(io.open(OUT .. TAG .. '_' .. tag .. '_cgram.bin', 'wb'))
  for a = 0, 511 do c:write(string.char(memory.read_u8(a, 'CGRAM'))) end
  c:close()
  client.screenshot(TAG .. '_' .. tag)
  line('dumped ' .. tag)
end

local function greenband()
  local n, ys = 0, {}
  for y = 96, 174, 2 do
    local row = 0
    for x = 0, 255, 4 do
      local ok, c = pcall(function() return client.getpixel(x, y) end)
      if ok and type(c) == 'number' then
        local r = c % 256
        local g = math.floor(c / 256) % 256
        local b = math.floor(c / 65536) % 256
        if g > 140 and r < 90 and b < 90 then row = row + 1 end
      end
    end
    if row > 8 then n = n + row; ys[#ys + 1] = y end
  end
  return n, ys
end

local dirs = { 'Right', 'Left', 'Down', 'Up' }
local hits = 0
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
  if f % 8 == 0 then client.screenshot(string.format('%s_f%05d', TAG, f)) end
  local n, ys = greenband()
  if n > 30 then
    hits = hits + 1
    line(string.format('HIT f=%d n=%d rows=%s', f, n, table.concat(ys, ',')))
    if hits <= 8 then dump(string.format('hit%02d_f%05d', hits, f)) end
  end
  if f % 600 == 0 then
    line(string.format('f%05d 6E=%02X 74=%02X 92=%02X 9E=%02X pend=%02X DF=%02X DD=%02X',
      f, w(0x036E), w(0x0374), w(0x0392), w(0x039E), w(0x0BFB), w(0x09DF), w(0x09DD)))
  end
end
line('done hits=' .. hits)