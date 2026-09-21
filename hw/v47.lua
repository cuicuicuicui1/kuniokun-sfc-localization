-- v47: dump the upload queue and the box cells while a wipe should be running.
local TAG = os.getenv('HW_TAG') or 'v47'
local FROM = tonumber(os.getenv('HW_FROM') or '1400')
local TO = tonumber(os.getenv('HW_TO') or '1445')
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v47 start tag=', TAG, '\n')

local function word(w)
  local b = w * 2
  return memory.read_u8(b, 'VRAM') + memory.read_u8(b + 1, 'VRAM') * 256
end

local frames = 0
while frames < TO do
  if frames >= FROM then
    local q = {}
    for i = 0, 0x80 do
      q[#q + 1] = string.format('%02X', memory.read_u8(0x0B00 + i, 'WRAM'))
    end
    local cells = {}
    for r = 0, 2 do
      local base = 0x7C00 + r * 0x40
      local up, lo = {}, {}
      for c = 0, 13 do
        up[#up + 1] = string.format('%03X', word(base + 3 + c) % 0x400)
        lo[#lo + 1] = string.format('%03X', word(base + 3 + 32 + c) % 0x400)
      end
      cells[#cells + 1] = string.format('r%d up=%s lo=%s', r, table.concat(up, ' '), table.concat(lo, ' '))
    end
    log:write(string.format('F=%d dd=%02X df=%02X T=%02X B=%02X CUR=%02X LO=%02X P=%02X col=%02X row=%02X e9=%02X\n%s\n  q=%s\n',
      frames,
      memory.read_u8(0x09DD, 'WRAM'), memory.read_u8(0x09DF, 'WRAM'),
      memory.read_u8(0x0D40, 'WRAM'), memory.read_u8(0x0D41, 'WRAM'),
      memory.read_u8(0x0D42, 'WRAM'), memory.read_u8(0x0D58, 'WRAM'),
      memory.read_u8(0x0D43, 'WRAM'),
      memory.read_u8(0x036F, 'WRAM'), memory.read_u8(0x036E, 'WRAM'),
      memory.read_u8(0x03E9, 'WRAM'),
      table.concat(cells, '\n'), table.concat(q, ' ')))
    log:flush()
  end
  if (emu.framecount() % 30) == 0 then joypad.set({ A = true }, 1) end
  if emu.framecount() < 420 and (emu.framecount() % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  frames = frames + 1
end
log:write('v47 done\n')
log:close()