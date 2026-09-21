-- menutest: tap through the story, press Start, and check the game keeps
-- running afterwards (a hang would freeze the scene) and whether the window's
-- label table got populated.
local TAG = os.getenv('HW_TAG') or 'menutest'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function nz() local n=0 for k=0,51 do if w(0x040A+k)~=0 then n=n+1 end end return n end
local function snap(name) client.screenshot(TAG .. '_' .. name) end
while emu.framecount() < 1300 do emu.frameadvance() end
for i = 1, 120 do
  for k = 0, 7 do joypad.set({A=true}); emu.frameadvance() end
  for k = 0, 22 do emu.frameadvance() end
end
log:write('story tapped, F=' .. emu.framecount() .. '\n')
snap('before')
-- press Start and watch
for round = 1, 6 do
  for k = 0, 7 do joypad.set({Start=true}); emu.frameadvance() end
  for k = 0, 60 do emu.frameadvance() end
  local f = emu.framecount()
  log:write(string.format('round %d F=%d  $040A nonzero=%d  row=%02X col=%02X\n',
    round, f, nz(), w(0x036E), w(0x036F)))
  snap('start' .. round)
  for k = 0, 90 do emu.frameadvance() end
  snap('later' .. round)
  log:flush()
end
log:write('done\n'); log:flush()
