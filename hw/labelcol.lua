-- labelcol: log every label-code draw with its buffer index, row and column
local OUT='C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log=assert(io.open(OUT..'labelcol.log','w'))
local function rd(a) return memory.read_u8(a,'WRAM') end
local last=nil
while emu.framecount() < 70000 do
  local i=emu.framecount()
  local p=rd(0x03E9)
  local b0=rd(0x03EA+p)
  local b1=rd(0x03EA+((p+1)%256))
  if b0>=0xC0 and b0<=0xDB and b1>=0x80 then
    local key=string.format('%d:%d:%d',p,rd(0x036E),rd(0x036F))
    if key~=last then
      last=key
      log:write(string.format('F=%d idx=%02X row=%02X col=%02X code=%02X id=%02X\n',i,p,rd(0x036E),rd(0x036F),b0,b1))
      log:flush()
    end
  end
  if i%8==0 then joypad.set({A=true}) end
  if i%90<5 then joypad.set({Start=true}) end
  emu.frameadvance()
end
log:write('done\n'); log:flush()
