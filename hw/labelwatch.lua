-- labelwatch: dump the label pair tiles every frame around a label draw
local OUT='C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log=assert(io.open(OUT..'labelwatch.log','w'))
local function rd(a) return memory.read_u8(a,'WRAM') end
local function vb(a) return memory.read_u8(a,'VRAM') end
-- tiles E6..FD -> VRAM byte (0x6000+t*8)*2
local tiles={}
for t=0xE6,0xFD do tiles[#tiles+1]=t end
local function snap()
  local s={}
  for _,t in ipairs(tiles) do
    local i=(0x6000+t*8)*2
    s[#s+1]=string.format('%02X%02X', vb(i), vb(i+1))
  end
  return table.concat(s,' ')
end
local fired=false; local last=-1
while emu.framecount() < 60000 do
  local i=emu.framecount()
  local p=rd(0x03E9); local b0=rd(0x03EA+p)
  local islbl = (b0>=0xC0 and b0<=0xDB) and rd(0x03EA+((p+1)%256))>=0x80
  if islbl and not fired then fired=true; last=i end
  if fired and i-last<=14 then
    log:write(string.format('F=%d idx=%02X row=%02X col=%02X 09DF=%02X tiles=%s\n',
      i, p, rd(0x036E), rd(0x036F), rd(0x09DF), snap()))
    log:flush()
  end
  if i%8==0 then joypad.set({A=true}) end
  if i%90<5 then joypad.set({Start=true}) end
  emu.frameadvance()
end
log:write('done\n'); log:flush()
