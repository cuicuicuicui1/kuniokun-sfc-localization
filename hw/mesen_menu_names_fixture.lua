-- CONTROLLED DIAGNOSTIC ONLY: level/inventory WRAM injected after same-ROM state load.
-- Not a natural inventory-acquisition playthrough. No PC/scene jump or player save writes.
-- Bounded headless interaction. No gameplay RAM patching; only pad input and
-- optional SRAM copy at boot. State loading/saving happens in exec callbacks.
local out=assert(os.getenv('PLAY_OUT'));local tag=assert(os.getenv('PLAY_TAG'))
local maxf=tonumber(os.getenv('PLAY_FRAMES') or '300')
local mem=emu.memType.snesMemory
local log=assert(io.open(out..'/'..tag..'.log','w'))
local function p(s) log:write(s..'\n');log:flush() end
local function r(a) return emu.read(a,mem)&255 end
local events={}
for lo,hi,keys in (os.getenv('PLAY_INPUT') or ''):gmatch('(%d+)%-(%d+):([%w,+]+)') do
 local buttons={} for k in keys:gmatch('%w+') do buttons[#buttons+1]=k end
 events[#events+1]={tonumber(lo),tonumber(hi),buttons}
end
local shots={}
for f in (os.getenv('PLAY_SHOTS') or '30'):gmatch('%d+') do shots[tonumber(f)]=true end
shots[maxf]=true
local hud=0;local plates={};local list=0;local item=0
local n=0;local ready=false;local wantSave=false
local state=os.getenv('PLAY_STATE') or ''
local seed=os.getenv('PLAY_SRAM') or ''
if seed~='' then
 assert(state=='','cannot load state and seed SRAM together')
 local g=assert(io.open(seed,'rb'));local data=g:read('*a');g:close()
 for i=1,#data do emu.write(i-1,data:byte(i),emu.memType.snesSaveRam) end
end
local function dump(label)
 local g=assert(io.open(out..'/'..tag..'-'..label..'.png','wb'));g:write(emu.takeScreenshot());g:close()
 for _,spec in ipairs({{'ram',mem,0x7E0000,0x2000},{'vram',emu.memType.snesVideoRam,0,0x10000}}) do
  g=assert(io.open(out..'/'..tag..'-'..label..'.'..spec[1],'wb'))
  local a={} for i=0,spec[4]-1 do a[#a+1]=string.char(emu.read(spec[3]+i,spec[2])&255) end
  g:write(table.concat(a));g:close()
 end
 local st=emu.getState();p(string.format('PAD %s held=%02X/%02X edge=%02X/%02X hw=%02X%02X cpu=%02X:%04X',label,r(0x31A),r(0x31C),r(0x316),r(0x318),r(0x4219),r(0x4218),st['cpu.k'],st['cpu.pc']))
 p(string.format('SHOT %s msg=%02X/%02X row=%02X col=%02X ix=%02X len=%02X',label,r(0x373),r(0x374),r(0x36E),r(0x36F),r(0x3E9),r(0x3E8)))
end
emu.addEventCallback(function()
 local key={a=false,b=false,x=false,y=false,up=false,down=false,left=false,right=false,start=false,select=false,l=false,r=false}
 if ready then for _,e in ipairs(events) do if n>=e[1] and n<e[2] then for _,k in ipairs(e[3]) do assert(key[k]~=nil,'unknown input '..k);key[k]=true end end end end
 emu.setInput(key,0)
 local actual=emu.getInput(0);for k,v in pairs(key) do assert(actual[k]==v,'input override failed: '..k) end
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
 if not ready then
  ready=true
  if state~='' then
   local g=assert(io.open(state,'rb'));local data=g:read('*a');g:close()
   assert(emu.loadSavestate(data),'loadSavestate failed');p('LOADED '..state)
   if (os.getenv('RUNTIME_FIXTURE') or '')=='menus' then
    emu.write(0x7E0102,99,mem)
    local ids={28,29,30,31,32,33,34,35}
    emu.write(0x7E011E,#ids,mem)
    for i,id in ipairs(ids) do emu.write(0x7E011E+i,id,mem) end
    p('FIXTURE: isolated runtime level=99 and 8 inventory IDs 28..35; no PC/scene change or save write')
   end

  else p('COLD BOOT') end
  return
 end
 if wantSave then
  wantSave=false
  local data=assert(emu.createSavestate());local g=assert(io.open(out..'/'..tag..'.state','wb'));g:write(data);g:close()
  p(string.format('COUNTS hud=%d list=%d item=%d',hud or 0,list or 0,item or 0));p('SAVED frames='..n);log:close();emu.stop(0)
 end
end,emu.callbackType.exec,0x8000,0xFFFF,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 hud=hud+1
 local plate=r(0x10);local char=r(0x18);local rec=''
 for j=0,3 do rec=rec..string.format('%02X',r(0x1b46+plate*4+j)) end
 local key=tostring(plate)..':'..rec
 if not plates[key] then
  plates[key]=true
  p(string.format('HUD f=%d slot=%d char=%d active=%02X rec=%s',n,plate,char,r(0x1c03+plate),rec))
 end
end,emu.callbackType.exec,0x3ED000,0x3ED000,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 list=list+1
 if list<15 then p(string.format('LIST f=%d row=%02X index=%02X q=%02X%02X data=%02X%02X%02X%02X',n,r(0x36e),r(0x39e),r(0x9e0),r(0x9df),r(0x40b),r(0x40c),r(0x40d),r(0x40e))) end
end,emu.callbackType.exec,0x3F95D,0x3F95D,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 item=item+1
 if item<25 then p(string.format('ITEM f=%d row=%02X col=%02X id=%02X',n,r(0x36e),r(0x36f),r(0x3ea+r(0x3e9)+1))) end
end,emu.callbackType.exec,0x3ED400,0x3ED400,emu.cpuType.snes,mem)
local draw=0
emu.addMemoryCallback(function()
 draw=draw+1
 if (os.getenv('PLAY_TRACE') or '')=='1' then p(string.format('DRAW f=%d ix=%02X len=%02X code=%02X row=%02X col=%02X held=%02X/%02X edge=%02X/%02X',n,r(0x3E9),r(0x3E8),r(0x12),r(0x36E),r(0x36F),r(0x31A),r(0x31C),r(0x316),r(0x318))) end
end,emu.callbackType.exec,0x3FA30,0x3FA30,emu.cpuType.snes,mem)
emu.addEventCallback(function()
 if not ready then return end
 n=n+1
 if shots[n] then dump(tostring(n)) end
 if n%300==0 then p(string.format('FRAME %d draws=%d held=%02X/%02X',n,draw,r(0x31A),r(0x31C))) end
 if n>=maxf then wantSave=true end
end,emu.eventType.endFrame)
