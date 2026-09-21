-- minimal liveness probe: heartbeats + a couple of scalars, nothing else
-- env: HW_TAG, HW_ROM (unused here), HW_LAST
local tag = os.getenv('HW_TAG') or 'v64'
local last = tonumber(os.getenv('HW_LAST') or '2600')
local path = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/' .. tag .. '.log'
local log = assert(io.open(path, 'w'))
log:write('start v64 last=', last, '\n')
log:flush()

pcall(function() emu.limitframerate(false) end)

local lm = ''
while emu.framecount() < last do
  local i = emu.framecount()
  if i % 60 == 0 then
    local e8 = memory.read_u8(0x03E8, 'WRAM')
    local e9 = memory.read_u8(0x03E9, 'WRAM')
    local col = memory.read_u8(0x036F, 'WRAM')
    local row = memory.read_u8(0x036E, 'WRAM')
    local dd = memory.read_u8(0x09DD, 'WRAM')
    local df = memory.read_u8(0x09DF, 'WRAM')
    local cur = string.format('H F=%d e8=%02X e9=%02X col=%02X row=%02X dd=%02X df=%02X', i, e8, e9, col, row, dd, df)
    if cur ~= lm then
      lm = cur
      log:write(cur)
      log:write(string.char(10))
      log:flush()
    end
  end
  if i == 150 or i == 300 or i == 450 then joypad.set({ Start = true }) end
  if i >= 200 and i % 20 == 0 then joypad.set({ A = true }) end
  emu.frameadvance()
end
log:write('done')
log:write(string.char(10))
log:flush()
log:close()