-- Real event08 continuation. ZERO WRAM or ROM writes after loading SAME-ROM state.
-- Requires msg-00C4 state prepared by mesen_umeda_jump.lua on the SAME ROM.
-- STORY_EXPECT=stall|advance asserts the old/new differential. No memory injection.
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
local checkpoint=nil;local halted=false
local expectation=os.getenv('STORY_EXPECT') or 'advance'
assert(expectation=='stall' or expectation=='advance','unknown STORY_EXPECT')
local state=assert(os.getenv('PLAY_STATE'),'same-ROM C4 state required')
assert(state~='', 'continuation requires a same-ROM C4 checkpoint')
assert((os.getenv('PLAY_SRAM') or '')=='','never seed SRAM in this fixture')
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
 if ready and r(0x373)~=0 and n%30<3 then key.a=true end
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
   assert(r(0x1D23)==0x88 and r(0x1D20)+256*r(0x1D21)==0xA3B5, 'not event08 C4 checkpoint')
  else p('COLD BOOT') end
  return
 end

 if checkpoint then
  local label=checkpoint;checkpoint=nil
  local data=assert(emu.createSavestate());local g=assert(io.open(out..'/'..tag..'-'..label..'.state','wb'));g:write(data);g:close()
  p('CHECKPOINT '..label..' frame='..n);dump(label)
 end
 if halted then return end
 if wantSave then
  wantSave=false
  local data=assert(emu.createSavestate());local g=assert(io.open(out..'/'..tag..'.state','wb'));g:write(data);g:close()
  halted=true;p('SAVED frames='..n);log:close();emu.stop(0)
 end
end,emu.callbackType.exec,0x7333,0x7333,emu.cpuType.snes,emu.memType.snesPrgRom)



local function status()
 local st=emu.getState()
 p(string.format('GAME f=%d map=%02X camera=%04X x=%04X event=%02X/%02X pc=%04X wait=%02X/%02X/%02X msg=%02X ix=%02X/%02X col=%02X train=%04X vel=%04X control=%02X q=%02X/%02X cpu=%02X:%04X',n,r(0x900),r(0x903)+256*r(0x904),r(0xE81)+256*r(0xE91),r(0x1D22),r(0x1D23),r(0x1D20)+256*r(0x1D21),r(0x1D25),r(0x1D26),r(0x1D27),r(0x373),r(0x3E9),r(0x3E8),r(0x36F),r(0xDE9)+256*r(0xDEA),r(0x9E0)+256*r(0x9E1),r(0xDE1),r(0x9DD),r(0x9DF),st['cpu.k'],st['cpu.pc']))
end
local frames5=nil;local deCalls=0;local firstProgress=nil;local train=0;local moving=0;local after5Train=0;local after5Moving=0;local vmCount=0;local progressedTo09=false
emu.addMemoryCallback(function()
 local pc=r(0x1D20)+256*r(0x1D21);vmCount=vmCount+1
 p(string.format('VM f=%d event=%02X pc=%04X op=%02X',n,r(0x1D23),pc,r(0x40000+pc)))
 if r(0x1D23)==0x89 then progressedTo09=true end
end,emu.callbackType.exec,0x38F1B,0x38F1B,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()
 local id=r(0x34A)+256*r(0x34B)
 p(string.format('MSG f=%d id=%04X speaker=%04X',n,id,r(0x34C)+256*r(0x34D)))
 if id==5 then frames5=n;checkpoint='msg-0005' end
end,emu.callbackType.exec,0x1EB07,0x1EB07,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()
 if frames5 and r(0x12)==0xDE then
  deCalls=deCalls+1
  if deCalls<=8 or deCalls%500==0 then
   p(string.format('DE f=%d calls=%d id=%02X ix=%02X col=%02X vel=%04X q=%02X/%02X',n,deCalls,r(0x3EA+r(0x3E9)+1),r(0x3E9),r(0x36F),r(0x9E0)+256*r(0x9E1),r(0x9DD),r(0x9DF)))
  end
 end
end,emu.callbackType.exec,0x1FA30,0x1FA30,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()
 train=train+1
 local active=(r(0x3B)~=0 or r(0x3C)~=0)
 if active then moving=moving+1 end
 if frames5 then after5Train=after5Train+1;if active then after5Moving=after5Moving+1 end end
end,emu.callbackType.exec,0x7C75,0x7C75,emu.cpuType.snes,emu.memType.snesPrgRom)
local main=0;local ticks=0
emu.addMemoryCallback(function() main=main+1 end,emu.callbackType.exec,0x7333,0x7333,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function() ticks=ticks+1 end,emu.callbackType.exec,0x1EE70,0x1EE70,emu.cpuType.snes,emu.memType.snesPrgRom)
local lastmap=-1
emu.addEventCallback(function()
 if not ready then return end
 n=n+1
 if frames5 and not firstProgress and r(0x3E9)>0 then firstProgress=n end
 if n%120==0 or r(0x900)~=lastmap then status();lastmap=r(0x900) end
 if shots[n] then dump(tostring(n)) end
 if n>=maxf then
  assert(frames5 and main>100 and ticks>100, 'empty story fixture: reward or real consumer not exercised')
  if expectation=='stall' then
   assert(not progressedTo09 and not firstProgress and deCalls>=100, 'old reward no longer stalls')
   assert(r(0x1D23)==0x88 and r(0x1D20)+256*r(0x1D21)==0xA3BE and r(0x373)~=0 and r(0x3E9)==0, 'not original reward wait')
  else
   assert(progressedTo09 and firstProgress and deCalls==3, 'reward failed or unnecessary retry')
   assert(after5Train>100 and after5Moving>100, 'train never resumed after reward')
  end
  p('PASS controlled original event08 continuation expectation='..expectation)
  p(string.format('RESULT frames=%d message5=%s DE=%d firstProgress=%s vm=%d event09=%s train=%d moving=%d after5Train=%d after5Moving=%d main=%d ticks=%d',n,tostring(frames5),deCalls,tostring(firstProgress),vmCount,tostring(progressedTo09),train,moving,after5Train,after5Moving,main,ticks));wantSave=true
 end
end,emu.eventType.endFrame)
