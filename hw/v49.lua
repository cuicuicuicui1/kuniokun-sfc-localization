-- v49: watch $0d00-$0dff for changes made by the game itself (run on the ORIGINAL rom)
-- so we know whether the scratch block the patch uses is really free.
local TAG = os.getenv('HW_TAG') or 'v49'
local FROM = tonumber(os.getenv('HW_FROM') or '1300')
local TO = tonumber(os.getenv('HW_TO') or '1620')
local LO = tonumber(os.getenv('HW_LO') or '0x0D00')
local HI = tonumber(os.getenv('HW_HI') or '0x0D00') + 0x100
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v49 start tag=', TAG, string.format(' range %04X-%04X', LO, HI - 1), '\n')

local prev = {}
for a = LO, HI - 1 do prev[a] = memory.read_u8(a, 'WRAM') end

local frames = 0
local changes = 0
while frames < TO do
  if (emu.framecount() % 30) == 0 then joypad.set({ A = true }, 1) end
  if emu.framecount() < 420 and (emu.framecount() % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  frames = frames + 1
  if frames >= FROM then
    for a = LO, HI - 1 do
      local v = memory.read_u8(a, 'WRAM')
      if v ~= prev[a] then
        log:write(string.format('F=%d %04X %02X -> %02X\n', frames, a, prev[a], v))
        prev[a] = v
        changes = changes + 1
      end
    end
    log:flush()
  end
end
log:write(string.format('v49 done, %d changes\n', changes))
log:close()