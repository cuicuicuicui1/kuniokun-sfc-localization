local OUT='C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log=assert(io.open(OUT..'prefix.log','w'))
local function rd(a) return memory.read_u8(a,'WRAM') end
local last=nil
while emu.framecount() < 70000 do
  local i=emu.framecount()
  local p=rd(0x03E9)
  if p<=2 then
    local b0=rd(0x03EA); local b1=rd(0x03EB)
    if b0>=0xC0 and b0<=0xDB and b1>=0x80 then
      local s={}
      for k=0,9 do s[#s+1]=string.format('%02X',rd(0x03EA+((p+k)%256))) end
      local key=table.concat(s,' ')
      if key~=last then
        last=key
        log:write(string.format('F=%d idx=%02X row=%02X col=%02X buf=%s\n',i,p,rd(0x036E),rd(0x036F),key))
        log:flush()
      end
    end
  end
  if i%8==0 then joypad.set({A=true}) end
  if i%90<5 then joypad.set({Start=true}) end
  emu.frameadvance()
end
log:write('done\n'); log:flush()
