-- v51: poke a marker into $0d40-$0d5f on the ORIGINAL rom, then log which of those bytes the
-- game itself changes (this shows whether the block is really free).
local TAG = os.getenv('HW_TAG') or 'v51'
local POKE_AT = tonumber(os.getenv('HW_FROM') or '1370')
local WATCH = tonumber(os.getenv('HW_TO') or '80')
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v51 start tag=', TAG, ' poke@', POKE_AT, '\n'); log:flush()

local LO, HI = 0x0D40, 0x0D60
local MARK = 0xA5
local poked = false
local prev = {}
local frames = 0
local endf = POKE_AT + WATCH
while frames < endf do
  if frames == POKE_AT then
    for a = LO, HI - 1 do
      memory.write_u8(a, MARK, 'WRAM')
      prev[a] = MARK
    end
    poked = true
    log:write(string.format('F=%d poked %02X into %04X-%04X\n', frames, MARK, LO, HI - 1))
    log:flush()
  end
  if (emu.framecount() % 30) == 0 then joypad.set({ A = true }, 1) end
  if emu.framecount() < 420 and (emu.framecount() % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  frames = frames + 1
  if poked then
    for a = LO, HI - 1 do
      local v = memory.read_u8(a, 'WRAM')
      if v ~= prev[a] then
        log:write(string.format('F=%d %04X %02X -> %02X\n', frames, a, prev[a], v))
        prev[a] = v
      end
    end
    log:flush()
  end
end
log:write('v51 done\n')
log:close()