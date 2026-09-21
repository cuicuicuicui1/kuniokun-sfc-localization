-- watchwin: run the game with gameplay inputs; poll the three name-widget
-- tilemap words ($79C6/$7A06/$7A46 -> VRAM bytes 0xF38C/0xF40C/0xF48C).
-- When any of them becomes non-blank, dump full VRAM + screenshot + log once
-- per opening, then keep playing.
-- env: HW_TAG HW_UNTIL
local TAG = os.getenv('HW_TAG') or 'watchwin'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '40000') or 40000
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local opens = 0
local last = {}
local cool = 0

local function rdw(byteoff) return memory.read_u8(byteoff, 'VRAM') + memory.read_u8(byteoff + 1, 'VRAM') * 256 end
local function dump(frame, which)
  opens = opens + 1
  local f = assert(io.open(string.format('%s%s_open%d_vram64.bin', OUT, TAG, opens), 'wb'))
  for i = 0, 0xFFFF do f:write(string.char(memory.read_u8(i, 'VRAM'))) end
  f:close()
  client.screenshot(string.format('%s_open%d_f%06d.png', TAG, opens, frame))
  log:write(string.format('F=%d OPEN%d which=%s w79C6=%04X w7A06=%04X w7A46=%04X\n',
    frame, opens, which, rdw(0xF38C), rdw(0xF40C), rdw(0xF48C)))
  log:flush()
end

while emu.framecount() < UNTIL do
  local i = emu.framecount()
  local cur = { rdw(0xF38C), rdw(0xF40C), rdw(0xF48C) }
  if cool > 0 then cool = cool - 1
  else
    for k = 1, 3 do
      if cur[k] ~= last[k] and cur[k] ~= 0x2C00 and cur[k] ~= 0 then
        dump(i, k)
        cool = 600
        break
      end
    end
  end
  last = cur
  if i == 150 or i == 300 or i == 450 then joypad.set({ Start = true }) end
  if i >= 200 and i % 20 == 0 then joypad.set({ A = true }) end
  if i > 900 and i % 120 < 50 then joypad.set({ Right = true }) end
  if i > 900 and i % 1200 == 1100 then joypad.set({ Select = true }) end
  emu.frameadvance()
end
log:write('done opens=' .. opens .. '\n')
log:flush()
