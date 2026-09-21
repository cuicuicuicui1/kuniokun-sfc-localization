-- v50: raw dump of the wipe scratch + box rows + queue cursors, one line per frame.
local TAG = os.getenv('HW_TAG') or 'v50'
local FROM = tonumber(os.getenv('HW_FROM') or '1540')
local TO = tonumber(os.getenv('HW_TO') or '1560')
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v50 start tag=', TAG, '\n'); log:flush()

local function u8(a) return memory.read_u8(a, 'WRAM') end
local function word(w)
  local b = w * 2
  return memory.read_u8(b, 'VRAM') + memory.read_u8(b + 1, 'VRAM') * 256
end

local frames = 0
while frames < TO do
  if frames >= FROM then
    local sc = {}
    for a = 0x0D40, 0x0D5F do sc[#sc + 1] = string.format('%02X', u8(a)) end
    local rows = {}
    for r = 0, 3 do
      local base = 0x7C00 + r * 0x40
      local n = 0
      for c = 0, 29 do
        local t = word(base + 3 + c) % 0x400
        if t ~= 0x200 and t ~= 0x000 then n = n + 1 end
      end
      local tt = {}
      for c = 0, 5 do tt[#tt + 1] = string.format('%03X', word(base + 3 + c) % 0x400) end
      rows[#rows + 1] = string.format('r%d[%d] %s', r, n, table.concat(tt, ' '))
    end
    log:write(string.format('F=%d  scratch=%s  dd=%02X df=%02X row=%02X col=%02X e9=%02X ln=%02X\n     %s\n',
      frames, table.concat(sc, ''), u8(0x09DD), u8(0x09DF), u8(0x036E), u8(0x036F), u8(0x03E9), u8(0x036D),
      table.concat(rows, ' | ')))
    log:flush()
  end
  if (emu.framecount() % 30) == 0 then joypad.set({ A = true }, 1) end
  if emu.framecount() < 420 and (emu.framecount() % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  frames = frames + 1
end
log:write('v50 done\n')
log:close()