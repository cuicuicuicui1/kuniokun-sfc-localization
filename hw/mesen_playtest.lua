-- Actual gameplay with scripted controller input. No CPU/RAM injection.
-- Optional existing Mesen state is loaded at an execution callback.
local out=assert(os.getenv('PLAY_OUT'))
local tag=assert(os.getenv('PLAY_TAG'))
local maxf=tonumber(os.getenv('PLAY_FRAMES') or '6000')
local state=os.getenv('PLAY_STATE') or ''
local mem=emu.memType.snesMemory
local f=assert(io.open(out..'/'..tag..'.log','w'))
local function p(s) f:write(s..'\n');f:flush() end
local function r(a) return emu.read(a,mem)&255 end
local key={a=false,b=false,x=false,y=false,up=false,down=false,left=false,right=false,start=false,select=false,l=false,r=false}
local n,hud,cells,status=0,0,0,0
local function shot(label)
 local g=assert(io.open(out..'/'..tag..'-'..label..'.png','wb'));g:write(emu.takeScreenshot());g:close()
end
if state~='' then
 local g=assert(io.open(state,'rb'));local blob=g:read('*a');g:close();local pending=true
 emu.addMemoryCallback(function()
  if pending then pending=false;assert(emu.loadSavestate(blob));p('loaded supplied state') end
 end,emu.callbackType.exec,0xF2AA,0xFFFF,emu.cpuType.snes,mem)
end
emu.addEventCallback(function() emu.setInput(key,0) end,emu.eventType.inputPolled)
emu.addMemoryCallback(function() hud=hud+1 end,emu.callbackType.exec,0x8C34,0x8C34,emu.cpuType.snes,mem)
emu.addMemoryCallback(function() cells=cells+1 end,emu.callbackType.exec,0x8C4B,0x8C4B,emu.cpuType.snes,mem)
emu.addMemoryCallback(function() status=status+1 end,emu.callbackType.exec,0x1F971,0x1F971,emu.cpuType.snes,mem)
emu.addEventCallback(function()
 n=n+1
 for k in pairs(key) do key[k]=false end
 if n>30 then
  if n<600 or r(0x373)~=0 or r(0x374)~=0 then key.a=(n%30)<3
  else
   local dirs={'right','down','left','up'}
   key[dirs[(math.floor(n/180)%4)+1]]=true
   key.a=n%40<3;key.y=n%23<4
  end
 end
 -- Try the Start menu only after the initial walking sample.
 if n>=2400 and n<2600 then
  for k in pairs(key) do key[k]=false end
  key.start=(n==2400)
  key.down=(n==2430 or n==2450 or n==2470)
  key.a=(n==2500)
 end
 if n==2620 then key.b=true end
 if n==30 or n==1800 or n==2550 or n==maxf then shot(tostring(n)) end
 if n%600==0 then p(string.format('frame=%d hud_calls=%d cell_returns=%d status_calls=%d msg=%02X/%02X pos=%02X%02X',n,hud,cells,status,r(0x373),r(0x374),r(0xB0E),r(0xB0F))) end
 if n>=maxf then p('COMPLETED controller-only gameplay sample');f:close();emu.stop(0) end
end,emu.eventType.endFrame)
