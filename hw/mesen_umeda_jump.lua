-- rc8 regression: preparation/save at physical ROM07333 (common F333 wait);
-- native gameplay F203 can be bypassed during prologue/menus.
-- Controlled preparation clears prior script waits; same-ROM gameplay seed
-- after prologue is required, not a cross-ROM or player-state workaround.
-- Controlled event08 jump: bypass entrance battle with original branch flag=1.
-- Only for isolated same-ROM hallway checkpoints, with the Start menu CLOSED.
-- Original VM installs event08; original spawner runs waves; controlled defeat
-- markers bypass fighting. No CPU/script PC, message-buffer or train-state writes.
-- ALL controlled WRAM writes end when original message00C4 starts.
-- Use mesen_umeda_continue.lua on the saved msg-00C4 state for zero-write proof.
-- Scene/branch/actor preparation is NOT a natural quest-completion test.
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
local checkpoint=nil;local checkpoints={};local messageCounts={};local halted=false
local postBattle=false;local qTrainWrites=0
local state=assert(os.getenv('PLAY_STATE'),'same-ROM checkpoint required')
assert(state~='', 'setup requires a same-ROM hallway checkpoint')
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


local forced=false;local mapped=false;local started=false
local function w(a,v) emu.write(a,v&255,mem) end
local function w16(a,v) w(a,v);w(a+1,v>>8) end
local function status(label)
 local s=emu.getState()
 p(string.format('%s f=%d map=%02X camera=%04X pos=%04X/%02X event=%02X/%02X pc=%04X wait=%02X/%02X/%02X ext=%02X/%02X/%02X/%02X fight=%02X/%02X train=%04X vel=%04X msg=%02X ix=%02X/%02X row=%02X col=%02X cpu=%02X:%04X',label,n,r(0x900),r(0x903)+256*r(0x904),r(0xE81)+256*r(0xE91),r(0xEB1),r(0x1D22),r(0x1D23),r(0x1D20)+256*r(0x1D21),r(0x1D25),r(0x1D26),r(0x1D27),r(0x1DA5),r(0x1DA6),r(0x1DA7),r(0x1DA8),r(0x122B),r(0x122D),r(0xDE9)+256*r(0xDEA),r(0x9E0)+256*r(0x9E1),r(0x373),r(0x3E9),r(0x3E8),r(0x36E),r(0x36F),s['cpu.k'],s['cpu.pc']))
end
emu.addMemoryCallback(function()

 if ready and started and not postBattle then
  w(0x10E,r(0x104))
  -- Jump preparation ONLY, disabled at C4, after all event08 battles.
  -- Satisfy original cinematic move targets before the requested battle endpoint.
  local vm=r(0x1D20)+256*r(0x1D21)
  if r(0x1D23)==0x88 and vm<0xA234 and (r(0x1D25)&2)~=0 then
   for i=0,1 do
    if r(0xE01+i)>=128 and (r(0x1D2C+i)&0x20)~=0 then
     local x=r(0x1D3A+i)+256*r(0x1D41+i)
     local y=r(0x1D48+i)+256*r(0x1D4F+i)
     w(0xE81+i,x&255);w(0xE91+i,x>>8);w(0xEB1+i,y&255);w(0xEC1+i,y>>8)
     w(0x92D+i,x&255);w(0x93D+i,x>>8);w(0x94D+i,y&255);w(0x95D+i,y>>8)
     w(0xE11+i,0x80);w(0xE21+i,0)
     p(string.format('CONTROLLED cinematic target f=%d vm=%04X actor=%d target=%04X/%04X',n,vm,i,x,y))
    end
   end
  end
  -- Controlled positioning satisfies ORIGINAL AE threshold checks, never skips VM commands.
  if (r(0x1D26)&2)~=0 and r(0x900)==r(0x1DDD) and r(0x1D23)==0x88 then
   local target=r(0x1DD7)+256*r(0x1DD8)
   local x=r(0xE81)+256*r(0xE91)
   if x<target then
    w(0xE81,(target+8)&255);w(0xE91,(target+8)>>8);w(0x92D,(target+8)&255);w(0x93D,(target+8)>>8)
    p(string.format('CONTROLLED position f=%d x=%04X for original AE threshold=%04X',n,target+8,target))
   end
  end
 end
 if ready and n>=60 and not forced then
  for _,a in ipairs({0x1D22,0x1D23,0x1D25,0x1D26,0x1D27,0x1DA5,0x1DA6,0x1DA7,0x1DA8,0x373,0x374,0x122B,0x122D,0x8D7}) do w(a,0) end
  forced=true;w(0x314,r(0x314)|0x40);p('CONTROLLED stop prior prologue branch then REQUEST original map reload')
 end
 if mapped and not started and n>100 then
  started=true
  -- Controlled equivalent of event08 branch1, after the entrance battle.
  -- This does NOT prove event07/rescue was naturally completed.
  w(0x1BE4,1);w(0x1D0C,0x88);w(0x1D22,0x88);w(0x1D23,0)
  for _,a in ipairs({0x1D25,0x1D26,0x1D27,0x1DA5,0x1DA6,0x1DA7,0x1DA8}) do w(a,0) end
  for i=0,6 do w(0x1D2C+i,0) end
  p('START controlled event08 through original $07:8760/$07:8AE3; no script-PC modification')
  status('START')
 end
end,emu.callbackType.exec,0x7333,0x7333,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()

 if forced and not mapped then
  mapped=true;w(0x900,0x13)
  -- Place players on the event08 entry side of the original platform map.
  local cam=0x580
  for _,a in ipairs({0x903,0x907,0x90B}) do w16(a,cam) end
  for i=0,1 do w(0xE81+i,0x88-i*16);w(0xE91+i,6);w(0xEB1+i,0x50);w(0xEC1+i,0) end
  w(0x010E,r(0x0104));p('MAP original loader scene13 camera0580; event08 branch1 after entrance battle')
 end
end,emu.callbackType.exec,0x7411,0x7411,emu.cpuType.snes,emu.memType.snesPrgRom)

local lastBattlePc=nil;local battleSince=0;local defeats=0
emu.addMemoryCallback(function()
 if not started or postBattle then return end
 local pc=r(0x1D20)+256*r(0x1D21)
 if r(0x122B)==1 and r(0x122D)==0 then
  if lastBattlePc~=pc then lastBattlePc=pc;battleSince=n end
  if n-battleSince>1 then
   local count=0
   for i=2,6 do
    if r(0xE01+i)==0x81 and r(0x1C60+i)>=128 and r(0x122F+i)==1 then
     w(0x122F+i,0);w(0xE11+i,0xE3);w(0xE01+i,0);count=count+1
    end
   end
   if count>0 then defeats=defeats+count;p(string.format('CONTROLLED defeated-count f=%d pc=%04X enemies=%d; inactive+defeated state; original $07:F211 detects completion',n,pc,count)) end
  end
 else lastBattlePc=nil end
end,emu.callbackType.exec,0x3F091,0x3F091,emu.cpuType.snes,emu.memType.snesPrgRom)
local cmds=0
emu.addMemoryCallback(function()
 if started then
  local pc=r(0x1D20)+256*r(0x1D21)
  cmds=cmds+1
  local a={} for i=0,7 do a[#a+1]=string.format('%02X',r(0x40000+pc+i)) end
  p(string.format('VM f=%d pc=04:%04X data=%s',n,pc,table.concat(a,' ')))
 end
end,emu.callbackType.exec,0x38F1B,0x38F1B,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()

 if started then
  local id=r(0x34A)+256*r(0x34B);messageCounts[id]=(messageCounts[id] or 0)+1
  p(string.format('MSG f=%d id=%04X speaker=%04X',n,id,r(0x34C)+256*r(0x34D)))
  if id>=0xBF and id<=0xC4 and not checkpoints[id] then
   checkpoints[id]=true;checkpoint=string.format('msg-%04X',id)
  end
  if id==0xC4 then postBattle=true end
 end
end,emu.callbackType.exec,0x1EB07,0x1EB07,emu.cpuType.snes,emu.memType.snesPrgRom)

local physical=assert(emu.memType.snesWorkRam)
emu.addMemoryCallback(function(address,value)
 local st=emu.getState()
 if started and st['cpu.k']>=0x20 then
  qTrainWrites=qTrainWrites+1
  if qTrainWrites<=12 then p(string.format('QUEUE_WROTE_TRAIN f=%d pc=%02X:%04X address=%06X value=%02X',n,st['cpu.k'],st['cpu.pc'],address,value)) end
 end
end,emu.callbackType.write,0x9E0,0x9E1,emu.cpuType.snes,physical)
local stores=0;local moving=0
emu.addMemoryCallback(function()
 stores=stores+1;if r(0x3B)~=0 or r(0x3C)~=0 then moving=moving+1 end
end,emu.callbackType.exec,0x7C75,0x7C75,emu.cpuType.snes,emu.memType.snesPrgRom)
local lastmap=-1
emu.addEventCallback(function()
 if not ready then return end
 n=n+1
 if n%120==0 or r(0x900)~=lastmap then status('GAME');lastmap=r(0x900);p(string.format('CONTROL train flags=%02X/%02X dir=%02X/%02X target=%04X counter=%02X queue=%02X/%02X',r(0xDE1),r(0xDE2),r(0xDEB),r(0xDEC),r(0xDED)+256*r(0xDEE),r(0x1C1D),r(0x9DD),r(0x9DF))) end
 if shots[n] then dump(tostring(n)) end
 if n>=maxf then assert(checkpoints[0xBF] and checkpoints[0xC0] and checkpoints[0xC4], 'setup did not reach original post-battle dialogue');p(string.format('END vm=%d train=%d moving=%d postBattle=%s qTrainWrites=%d',cmds,stores,moving,tostring(postBattle),qTrainWrites));wantSave=true end
end,emu.eventType.endFrame)
