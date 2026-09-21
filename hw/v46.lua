-- v46: watch the whole box (rows 0..3) while a new message entry arms the wipe.
-- Logs, per frame: the upper/lower half words of rows 0..3, the text buffer, the
-- engine's cursor, and my wipe state (TOP BOT CUR LO PEND).
local TAG = os.getenv('HW_TAG') or 'v46'
local FROM = tonumber(os.getenv('HW_FROM') or '1330')
local TO = tonumber(os.getenv('HW_TO') or '1620')
local SHOTS = os.getenv('HW_SHOTS') or ''
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v46 start tag=', TAG, ' from=', FROM, ' to=', TO, '\n')

local function word(w)
  local b = w * 2
  return memory.read_u8(b, 'VRAM') + memory.read_u8(b + 1, 'VRAM') * 256
end

local shots = {}
for s in string.gmatch(SHOTS, '%d+') do shots[tonumber(s)] = true end

local frames = 0
while frames < TO do
  local f = emu.framecount()
  if frames >= FROM then
    local parts = {}
    for r = 0, 3 do
      local base = 0x7C00 + r * 0x40
      local up, lo = {}, {}
      for c = 0, 27 do
        up[#up + 1] = string.format('%03X', word(base + 3 + c) % 0x400)
        lo[#lo + 1] = string.format('%03X', word(base + 3 + 32 + c) % 0x400)
      end
      parts[#parts + 1] = string.format('r%d %s | %s', r,
                                        table.concat(up, ' '), table.concat(lo, ' '))
    end
    local buf = {}
    for i = 0, 21 do
      buf[#buf + 1] = string.format('%02X', memory.read_u8(0x03EA + i, 'WRAM'))
    end
    log:write(string.format('F=%d %s\n  buf=%s\n  e8=%02X e9=%02X col=%02X row=%02X ln=%02X 73=%02X dd=%02X df=%02X wipe T=%02X B=%02X CUR=%02X LO=%02X P=%02X\n',
      frames, table.concat(parts, '\n'), table.concat(buf, ' '),
      memory.read_u8(0x03E8, 'WRAM'), memory.read_u8(0x03E9, 'WRAM'),
      memory.read_u8(0x036F, 'WRAM'), memory.read_u8(0x036E, 'WRAM'),
      memory.read_u8(0x036D, 'WRAM'), memory.read_u8(0x0373, 'WRAM'),
      memory.read_u8(0x09DD, 'WRAM'), memory.read_u8(0x09DF, 'WRAM'),
      memory.read_u8(0x0D40, 'WRAM'), memory.read_u8(0x0D41, 'WRAM'),
      memory.read_u8(0x0D42, 'WRAM'), memory.read_u8(0x0D58, 'WRAM'),
      memory.read_u8(0x0D43, 'WRAM')))
    log:flush()
    if shots[frames] then
      local png = string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s_f%05d.png', TAG, frames)
      client.screenshot(png)
      log:write('shot ' .. png .. '\n')
      log:flush()
    end
  end
  if (f % 30) == 0 then joypad.set({ A = true }, 1) end
  if f < 420 and (f % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  frames = frames + 1
end
local png = string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s_end.png', TAG)
client.screenshot(png)
log:write('v46 done, end shot ' .. png .. '\n')
log:close()