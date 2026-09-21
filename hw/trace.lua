local OUT='C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log=assert(io.open(OUT..'trace.log','w'))
local function rd(a) return memory.read_u8(a,'WRAM') end
while emu.framecount() < 1700 do
  local i=emu.framecount()
  if i>=1590 and i<=1640 then
    log:write(string.format('F=%d idx=%02X row=%02X col=%02X 12=%02X 73=%02X 09DF=%02X 03E8=%02X\n',
      i,rd(0x03E9),rd(0x036E),rd(0x036F),rd(0x12),rd(0x0373),rd(0x09DF),rd(0x03E8)))
    log:flush()
  end
  if i%8==0 then joypad.set({A=true}) end
  if i%90<5 then joypad.set({Start=true}) end
  emu.frameadvance()
end
log:write('done\n'); log:flush()
