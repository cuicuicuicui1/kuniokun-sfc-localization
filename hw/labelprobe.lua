-- labelprobe: drive the game until translated text is on screen, then record
-- the label row's tile map words and the message buffer, so the label's tile
-- pairs can be compared with the slot table.
-- env: HW_TAG HW_UNTIL HW_ROM
local TAG   = os.getenv('HW_TAG') or 'labelprobe'
local ROMF  = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '70000') or 70000
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)

local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function rd(a) return memory.read_u8(a, 'WRAM') end
local function vramb(a) return memory.read_u8(a, 'VRAM') end
-- the VRAM domain is addressed in bytes: word $7c00 is byte $f800
local function vramw(w) return vramb(w * 2) + vramb(w * 2 + 1) * 256 end

local function label_words()
  -- the message row is the engine's row counter, not row 0
  local r = rd(0x036E)
  local t = { string.format('r%02X', r) }
  for c = 3, 12 do
    t[#t + 1] = string.format('%04X', vramw(0x7C00 + r * 0x40 + c))
  end
  return table.concat(t, ' ')
end

local function dump_vram(frame)
  local f = assert(io.open(string.format('%s%s_f%05d_vram.bin', OUT, TAG, frame), 'wb'))
  for i = 0, 0x3FFF do f:write(string.char(memory.read_u8(0xC000 + i, 'VRAM'))) end
  f:close()
end

local function buf_bytes()
  local p = rd(0x03E9)
  local t = {}
  for i = 0, 15 do
    t[#t + 1] = string.format('%02X', rd(0x03EA + ((p + i) % 256)))
  end
  return table.concat(t, ' ')
end

local function cn_seen()
  local p = rd(0x03E9)
  for i = 0, 20 do
    local b = rd(0x03EA + ((p + i) % 256))
    if b >= 0xC0 and b <= 0xDB then return true end
  end
  return false
end

local shots, last = 0, -1000
while emu.framecount() < UNTIL do
  local i = emu.framecount()
  if cn_seen() and i - last >= 45 and shots < 80 then
    last = i
    shots = shots + 1
    log:write(string.format('F=%d 73=%02X 09DF=%02X label=%s buf=%s\n',
      i, rd(0x0373), rd(0x09DF), label_words(), buf_bytes()))
    log:flush()
    dump_vram(i)
    client.screenshot(string.format('%s_f%05d.png', TAG, i))
  end
  -- A advances dialogue, Start clears menus and the naming screen
  if i % 8 == 0 then joypad.set({A = true}) end
  if i % 90 < 5 then joypad.set({Start = true}) end
  emu.frameadvance()
end
log:write('done shots=' .. shots .. '\n')
log:flush()
