-- watch box row 0 cells + the line buffer + wipe state, frame by frame around a wipe
local TAG = os.getenv('HW_TAG') or 'v45'
local FROM = tonumber(os.getenv('HW_FROM') or '1405')
local TO = tonumber(os.getenv('HW_TO') or '1445')
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v45 start tag=', TAG, '\n')

local function word(w)
  local b = w * 2
  return memory.read_u8(b, 'VRAM') + memory.read_u8(b + 1, 'VRAM') * 256
end

local frames = 0
while frames < TO do
  if frames >= FROM then
    local up, lo = {}, {}
    for c = 3, 15 do
      up[#up + 1] = string.format('%03X', word(0x7C00 + 3 + c) % 0x400)
      lo[#lo + 1] = string.format('%03X', word(0x7C00 + 3 + 32 + c) % 0x400)
    end
    local buf = {}
    for i = 0, 17 do buf[#buf + 1] = string.format('%02X', memory.read_u8(0x03EA + i, 'WRAM')) end
    log:write(string.format('F=%d up=%s lo=%s e8=%02X e9=%02X col=%02X row=%02X ln=%02X 73=%02X wipe=%02X/%02X/%02X/%02X buf=%s\n',
      frames, table.concat(up, ' '), table.concat(lo, ' '),
      memory.read_u8(0x03E8, 'WRAM'), memory.read_u8(0x03E9, 'WRAM'),
      memory.read_u8(0x036F, 'WRAM'), memory.read_u8(0x036E, 'WRAM'), memory.read_u8(0x036D, 'WRAM'),
      memory.read_u8(0x0373, 'WRAM'),
      memory.read_u8(0x0D40, 'WRAM'), memory.read_u8(0x0D41, 'WRAM'), memory.read_u8(0x0D42, 'WRAM'), memory.read_u8(0x0D43, 'WRAM'),
      table.concat(buf, '')))
    log:flush()
  end
  local f = emu.framecount()
  if (f % 30) == 0 then joypad.set({ A = true }, 1) end
  if f < 420 and (f % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  frames = frames + 1
end
log:write('v45 done\n')
log:close()