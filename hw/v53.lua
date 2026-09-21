-- v53: raw change-dump of the wipe scratch ($0d40-$0d5f) + the queue cursors, every frame.
-- Prints the *full* 32-byte hex line whenever anything changes, so the write sequence can be
-- reconstructed exactly (no assumptions about which byte means what).
local TAG = os.getenv('HW_TAG') or 'v53'
local FROM = tonumber(os.getenv('HW_FROM') or '1370')
local TO = tonumber(os.getenv('HW_TO') or '1620')
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v53 scratch dump ', FROM, '..', TO, '\n')

local LO, HI = 0x0D40, 0x0D60
local prev = nil
local f = 0
while f < TO do
  if f >= FROM then
    local cur = {}
    for a = LO, HI - 1 do cur[#cur + 1] = memory.read_u8(a, 'WRAM') end
    local line = ''
    for i = 1, #cur do line = line .. string.format('%02X', cur[i]) end
    local dd = memory.read_u8(0x09DD, 'WRAM')
    local df = memory.read_u8(0x09DF, 'WRAM')
    local r73 = memory.read_u8(0x0373, 'WRAM')
    local col = memory.read_u8(0x036F, 'WRAM')
    local row = memory.read_u8(0x036E, 'WRAM')
    local key = line .. string.format('%02X%02X%02X%02X%02X', dd, df, r73, col, row)
    if key ~= prev then
      log:write(string.format('F=%d  0d40=%s  dd=%02X df=%02X 73=%02X col=%02X row=%02X\n', f, line, dd, df, r73, col, row))
      log:flush()
      prev = key
    end
  end
  if (emu.framecount() % 30) == 0 then joypad.set({ A = true }, 1) end
  if emu.framecount() < 420 and (emu.framecount() % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  f = f + 1
end
log:write('v53 done\n')
log:close()