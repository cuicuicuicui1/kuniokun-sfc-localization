-- watch the VRAM queue ($0B00) and the wipe state machine ($0D40-$0D43)
-- print any wipe header found in the queue: [$7C40+row*$40+3, $80, $34] and its +$20 twin
local TAG = os.getenv('HW_TAG') or 'v44'
local FROM = tonumber(os.getenv('HW_FROM') or '1370')
local TO = tonumber(os.getenv('HW_TO') or '1480')
local STEP = tonumber(os.getenv('HW_STEP') or '1')
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v44 start tag=', TAG, '\n')
log:flush()

local frames = 0
while frames < TO do
  if frames >= FROM and (frames % STEP) == 0 then
    local dd = memory.read_u8(0x09DD, 'WRAM')
    local df = memory.read_u8(0x09DF, 'WRAM')
    local top, bot, cur, pend = memory.read_u8(0x0D40, 'WRAM'), memory.read_u8(0x0D41, 'WRAM'),
      memory.read_u8(0x0D42, 'WRAM'), memory.read_u8(0x0D43, 'WRAM')
    local hits = {}
    for o = 0, 0xFC do
      local a = memory.read_u8(0x0B00 + o, 'WRAM')
      local h = memory.read_u8(0x0B00 + o + 1, 'WRAM')
      local v = memory.read_u8(0x0B00 + o + 2, 'WRAM')
      local c = memory.read_u8(0x0B00 + o + 3, 'WRAM')
      if h == 0x7C and v == 0x80 and c == 0x34 then
        hits[#hits + 1] = string.format('%02X:%02X', o, a)
      end
    end
    log:write(string.format('F=%d dd=%02X df=%02X top=%02X bot=%02X cur=%02X pend=%02X wipehdr=%s\n',
      frames, dd, df, top, bot, cur, pend, table.concat(hits, ',')))
    log:flush()
  end
  local f = emu.framecount()
  if (f % 30) == 0 then joypad.set({ A = true }, 1) end
  if f < 420 and (f % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  frames = frames + 1
end
log:write('v44 done\n')
log:close()