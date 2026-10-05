-- CONTROLLED train/text queue regression; NEVER a natural story reproduction.
-- Requires a same-ROM checkpoint with the Start menu CLOSED. Scene reload and
-- two-byte DE/body message injection are explicit disposable WRAM fixtures.
-- QUEUE_KIND=item|body; QUEUE_DIRECTION=right|left; QUEUE_EXPECT=advance|stall.
-- No CPU PC changes, ROM modifications, player save writes or emulator config writes.
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
 for _,spec in ipairs({{'ram',mem,0x7E0000,0x20000},{'vram',emu.memType.snesVideoRam,0,0x10000}}) do
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
  else p('COLD BOOT') end
  return
 end
 if wantSave then
  wantSave=false
  local data=assert(emu.createSavestate());local g=assert(io.open(out..'/'..tag..'.state','wb'));g:write(data);g:close()
  p('SAVED frames='..n);log:close();emu.stop(0)
 end
end,emu.callbackType.exec,0x8000,0xFFFF,emu.cpuType.snes,mem)

-- CONTROLLED fixture: reload via the original maploader, then replace one
-- message buffer while the original train updater is producing displacement.
-- This is a real CPU consumer test, NOT the player's quest route.
local forced=false;local mapped=false;local injectFrame=nil
local kind=os.getenv('QUEUE_KIND') or 'item'
local reversed=false
local expectation=os.getenv('QUEUE_EXPECT') or 'advance'
assert(expectation=='advance' or expectation=='stall','unknown QUEUE_EXPECT')
local code=(kind=='body') and 0xC6 or 0xDE
local ident=(kind=='body') and 0 or 0x3C
local trainStores=0;local movingStores=0;local itemCalls=0;local queueTrainWrites=0
local colAdvanced=false;local tickAfter=0
emu.addMemoryCallback(function()
 if ready and n>=2 and not forced then
  forced=true;emu.write(0x0314,r(0x0314)|0x40,mem)
 end
end,emu.callbackType.exec,0xF203,0xF203,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 if forced and not mapped then
  mapped=true
  local camera=0x900
  emu.write(0x0900,0x27,mem)
  for _,a in ipairs({0x0903,0x0907,0x090B}) do emu.write(a,camera&255,mem);emu.write(a+1,camera>>8,mem) end
  emu.write(0x0E81,(camera+128)&255,mem);emu.write(0x0E91,(camera+128)>>8,mem)
  emu.write(0x092D,(camera+128)&255,mem);emu.write(0x093D,(camera+128)>>8,mem)
  emu.write(0x0EB1,0x50,mem);emu.write(0x094D,0x50,mem)
  emu.write(0x010E,r(0x0104),mem)
  p('CONTROLLED scene 27 camera0900; quest flags not set; not natural story progression')
 end
end,emu.callbackType.exec,0xF411,0xF411,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 if mapped and n>120 and (os.getenv('QUEUE_DIRECTION') or '')=='left' and not reversed then
  reversed=true;emu.write(0xDEB,1,mem);emu.write(0xDEC,0,mem)
  p('CONTROLLED direction left; subsequent signed displacement produced by ORIGINAL updater')
 end
 trainStores=trainStores+1
 if r(0x3B)~=0 or r(0x3C)~=0 then movingStores=movingStores+1 end
end,emu.callbackType.exec,0xFC75,0xFC75,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 if not mapped then return end
 local velocity=r(0x9E0)+256*r(0x9E1)
 if n>150 and velocity~=0 and ((os.getenv('QUEUE_DIRECTION') or '')~='left' or velocity>=0xFF00) and not injectFrame then
  injectFrame=n
  -- Same message ABI as the model, entered via ORIGINAL $03:EE70.
  emu.write(0x373,0xC0,mem);emu.write(0x374,0,mem)
  emu.write(0x3E8,2,mem);emu.write(0x3E9,0,mem)
  emu.write(0x3EA,code,mem);emu.write(0x3EB,ident,mem)
  emu.write(0x36E,5,mem);emu.write(0x36F,0,mem)
  emu.write(0x3E7,0,mem)
  p(string.format('INJECT f=%d real_velocity=%04X queue=%02X/%02X kind=%s code=%02X id=%02X',n,velocity,r(0x9DD),r(0x9DF),kind,code,ident))
 end
 if injectFrame then tickAfter=tickAfter+1 end
end,emu.callbackType.exec,0x3EE70,0x3EE70,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 if injectFrame and r(0x12)==code then
  itemCalls=itemCalls+1
  if itemCalls<8 then p(string.format('LIVE glyph f=%d index=%02X col=%02X velocity=%04X cursor=%02X',n,r(0x3E9),r(0x36F),r(0x9E0)+256*r(0x9E1),r(0x9DF))) end
 end
end,emu.callbackType.exec,0x3FA30,0x3FA30,emu.cpuType.snes,mem)
local physical=assert(emu.memType.snesWorkRam,'physical WRAM domain unavailable')
emu.addMemoryCallback(function(address,value)
 local st=emu.getState()
 if injectFrame and st['cpu.k']==0x3E then
  queueTrainWrites=queueTrainWrites+1
  if queueTrainWrites<8 then p(string.format('BAD queue wrote train f=%d pc=%02X:%04X addr=%06X value=%02X',n,st['cpu.k'],st['cpu.pc'],address,value)) end
 end
end,emu.callbackType.write,0x9E0,0x9E1,emu.cpuType.snes,physical)
emu.addEventCallback(function()
 if injectFrame and r(0x36F)>0 then colAdvanced=true end
 if injectFrame and n==injectFrame+60 then
  assert(movingStores>10 and itemCalls>0 and tickAfter>0,'empty fixture: consumer/train not exercised')
  if expectation=='advance' then
   assert(colAdvanced and queueTrainWrites==0,'text stalled or corrupted train displacement')
  else
   assert(not colAdvanced and itemCalls>=5,'old negative no longer demonstrates retry stall')
  end
  p('PASS controlled early response: expected '..expectation..'; not natural story acceptance')
 end
 if n==maxf then assert(injectFrame and n>=injectFrame+60,'fixture never reached moving train/message consumer') end
 if injectFrame and (n==injectFrame+10 or n==injectFrame+60 or n==injectFrame+300 or n==maxf) then
  p(string.format('EVIDENCE f=%d inject=%d train=%d moving=%d items=%d ticks=%d colAdvanced=%s qWritesTrain=%d index=%02X col=%02X msg=%02X velocity=%04X',n,injectFrame,trainStores,movingStores,itemCalls,tickAfter,tostring(colAdvanced),queueTrainWrites,r(0x3E9),r(0x36F),r(0x373),r(0x9E0)+256*r(0x9E1)))
 end
end,emu.eventType.endFrame)
local lastmap=-1
local function actors()
 local list={}
 for i=0,15 do if r(0xE01+i)>=128 then
  list[#list+1]=string.format('%d:%02X,%04X,%02X,%02X,%02X',i,r(0xE01+i),r(0xE81+i)+256*r(0xE91+i),r(0xEB1+i),r(0xE11+i),r(0xE61+i))
 end end
 return table.concat(list,' ')
end
local function status()
 local s=emu.getState()
 p(string.format('GAME f=%d map=%02X camera=%04X pos=%04X/%02X level=%d hp=%d/%d flags=%02X/%02X/%02X train=%04X q8=%02X/%02X neighbors=%02X/%04X cpu=%02X:%04X sp=%04X actors=[%s]',n,r(0x900),r(0x903)+256*r(0x904),r(0xE81)+256*r(0xE91),r(0xEB1),r(0x102),r(0x10E),r(0x104),r(0x313),r(0x314),r(0x1CA5),r(0xDE9)+256*r(0xDEA),r(0x9DD),r(0x9DF),r(0x9DE),r(0x9E0)+256*r(0x9E1),s['cpu.k'],s['cpu.pc'],s['cpu.sp'],actors()))
end
local draw=0
emu.addMemoryCallback(function()
 draw=draw+1
 if (os.getenv('PLAY_TRACE') or '')=='1' then p(string.format('DRAW f=%d ix=%02X len=%02X code=%02X row=%02X col=%02X held=%02X/%02X edge=%02X/%02X',n,r(0x3E9),r(0x3E8),r(0x12),r(0x36E),r(0x36F),r(0x31A),r(0x31C),r(0x316),r(0x318))) end
end,emu.callbackType.exec,0x3FA30,0x3FA30,emu.cpuType.snes,mem)
emu.addEventCallback(function()
 if not ready then return end
 n=n+1
 if n%120==0 or r(0x900)~=lastmap then status();lastmap=r(0x900) end
 if shots[n] then dump(tostring(n)) end
 if n%300==0 then p(string.format('FRAME %d draws=%d held=%02X/%02X',n,draw,r(0x31A),r(0x31C))) end
 if n>=maxf then wantSave=true end
end,emu.eventType.endFrame)
