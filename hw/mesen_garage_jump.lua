-- rc8 regression: preparation/save at physical ROM07333 (common F333 wait);
-- native gameplay F203 can be bypassed during prologue/menus.
-- Controlled preparation clears prior script waits; same-ROM gameplay seed
-- after prologue is required, not a cross-ROM or player-state workaround.
-- CONTROLLED garage-event15 fixture, Kunio-kun only (2026-10-02).
-- Requires a SAME-ROM gameplay checkpoint, native main-loop $00:F203 and
-- Start menu closed. Earlier story branches/scene positions are prepared via
-- WRAM. Original loader installs maps and original VM installs event15.
-- No CPU/script-PC edits and no production patch. Earlier fights use inactive
-- markers; the final three-enemy fight DOES NOT. Starting HP is reduced to1
-- once, then ordinary controller attacks run original KO/XP/reward handling.
-- ALL Lua memory writes stop at final-battle start BEFORE original KO/XP.
-- This proves only the named consumers; not the user's natural story, normal
-- enemy strength, exact180 XP, Riki CPU setup, or a localization bug being fixed.
-- tools/run_garage_story.py records ROM identity, same-ROM checkpoint metadata,
-- preparation scope and separate INPUT-ONLY continuation. Use isolated outputs.
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
local postBattle=false;local qTrainWrites=0;local battlePrepared=false;local writeCount=0;local prepareEndWrites=nil;local prepareEndFrame=nil
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
 if ready and battlePrepared and r(0x1D23)==0x95 and (r(0x1D20)+256*r(0x1D21))==0xB94B and r(0x122B)==1 and r(0x122D)==0 and r(0x373)==0 then
  local x=r(0xE81)+256*r(0xE91);local y=r(0xEB1);local target=nil;local score=99999
  for i=4,6 do
   if r(0xE01+i)==0x81 and r(0x122F+i)==1 and r(0x12A6+i)>0 then
    local dx=r(0xE81+i)+256*r(0xE91+i)-x;local dy=r(0xEB1+i)-y
    local dist=math.abs(dx)+3*math.abs(dy)
    if dist<score then target={dx,dy};score=dist end
   end
  end
  if target then
   local dx,dy=target[1],target[2]
   if math.abs(dy)>3 then key.up=dy>0;key.down=dy<0 end
   if math.abs(dx)>16 then key.right=dx>0;key.left=dx<0 end
   if math.abs(dx)<=35 and math.abs(dy)<=6 then key.y=n%10<3;key.right=dx>0;key.left=dx<0 end
  end
 end
 if ready and r(0x373)~=0 and n%30<3 then key.a=true end
 if ready then for _,e in ipairs(events) do if n>=e[1] and n<e[2] then for _,k in ipairs(e[3]) do assert(key[k]~=nil,'unknown input '..k);key[k]=true end end end end
 emu.setInput(key,0)
 local actual=emu.getInput(0);for k,v in pairs(key) do assert(actual[k]==v,'input override failed: '..k) end
end,emu.eventType.inputPolled)
-- One cold-reset exec hook loads the checkpoint; lifecycle work then runs
-- only at the ORIGINAL gameplay main-loop boundary, not every instruction.
emu.addMemoryCallback(function()
 if ready then return end
 ready=true
 local g=assert(io.open(state,'rb'));local data=g:read('*a');g:close()
 assert(emu.loadSavestate(data),'loadSavestate failed');p('LOADED '..state)
end,emu.callbackType.exec,0x3D36,0x3D36,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()
 if not ready or halted then return end
 if checkpoint then
  local label=checkpoint;checkpoint=nil
  local data=assert(emu.createSavestate())
  local g=assert(io.open(out..'/'..tag..'-'..label..'.state','wb'));g:write(data);g:close()
  p('CHECKPOINT '..label..' frame='..n);dump(label)
 end
 if wantSave then
  wantSave=false;halted=true
  local data=assert(emu.createSavestate())
  local g=assert(io.open(out..'/'..tag..'.state','wb'));g:write(data);g:close()
  p(string.format('FRAME_BOUND actual=%d maximum=%d',n,maxf));p('SAVED frames='..n)
  log:close();emu.stop(0)
 end
end,emu.callbackType.exec,0x7333,0x7333,emu.cpuType.snes,emu.memType.snesPrgRom)


local forced=false;local mapped=false;local started=false;local wantMap=nil;local garageMapped=false
local function w(a,v)
 assert(not postBattle,'fixture attempted WRAM write after preparation stopped')
 writeCount=writeCount+1;emu.write(a,v&255,mem)
end
local function w16(a,v) w(a,v);w(a+1,v>>8) end
local function status(label)
 local s=emu.getState()
 p(string.format('%s f=%d map=%02X camera=%04X pos=%04X/%02X event=%02X/%02X pc=%04X wait=%02X/%02X/%02X ext=%02X/%02X/%02X/%02X fight=%02X/%02X train=%04X vel=%04X msg=%02X ix=%02X/%02X row=%02X col=%02X cpu=%02X:%04X',label,n,r(0x900),r(0x903)+256*r(0x904),r(0xE81)+256*r(0xE91),r(0xEB1),r(0x1D22),r(0x1D23),r(0x1D20)+256*r(0x1D21),r(0x1D25),r(0x1D26),r(0x1D27),r(0x1DA5),r(0x1DA6),r(0x1DA7),r(0x1DA8),r(0x122B),r(0x122D),r(0xDE9)+256*r(0xDEA),r(0x9E0)+256*r(0x9E1),r(0x373),r(0x3E9),r(0x3E8),r(0x36E),r(0x36F),s['cpu.k'],s['cpu.pc']))
end
emu.addMemoryCallback(function()

 if ready and started and not postBattle then
  w(0x10E,r(0x104))
  -- Scene and cinematic preparation ONLY, disabled at final-battle start.
  -- Satisfy original cinematic move targets before the requested battle endpoint.
  local vm=r(0x1D20)+256*r(0x1D21)
  if vm==0xB7A3 and not garageMapped then
   garageMapped=true;wantMap=0x4B;w(0x314,r(0x314)|0x40)
   p('CONTROLLED parking scene4B for original garage script, no door writes')
  end
  if (r(0x1D26)&2)~=0 and r(0x900)~=r(0x1DDD) and r(0x1D23)==0x95 and not wantMap then
   wantMap=r(0x1DDD);w(0x314,r(0x314)|0x40)
   p(string.format('CONTROLLED follow original AE scene threshold map=%02X',wantMap))
  end
  if r(0x1D23)==0x95 and vm<0xB98F and (r(0x1D25)&2)~=0 then
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
  if (r(0x1D26)&2)~=0 and r(0x900)==r(0x1DDD) and r(0x1D23)==0x95 then
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
  -- Controlled event15 stage selector; earlier entrance battles are bypassed.
  -- This does NOT prove event07/rescue was naturally completed.
  w(0x1BE4,0);w(0x1D0C,0x95);w(0x1D22,0x95);w(0x1D23,0)
  for _,a in ipairs({0x1D25,0x1D26,0x1D27,0x1DA5,0x1DA6,0x1DA7,0x1DA8}) do w(a,0) end
  for i=0,6 do w(0x1D2C+i,0) end
  p('START controlled event15 through original $07:8760/$07:8AE3; no script-PC modification')
  status('START')
 end
end,emu.callbackType.exec,0x7333,0x7333,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()

 if wantMap then
  local id=wantMap;wantMap=nil;w(0x900,id)
  local x=id==0x4B and 0x4C0 or r(0x1DD7)+256*r(0x1DD8)+16
  for _,a in ipairs({0x903,0x907,0x90B}) do w16(a,math.max(0,x-128)) end
  w16(0xE81,x&255);w(0xE91,x>>8);w(0xEB1,0x50)
  p(string.format('CONTROLLED original map reload=%02X',id))
 end
 if forced and not mapped then
  mapped=true;w(0x900,0x1C)
  -- Place players on the event15 street-side entry, before original garage script.
  local cam=0x700
  for _,a in ipairs({0x903,0x907,0x90B}) do w16(a,cam) end
  for i=0,1 do w(0xE81+i,0x95-i*16);w(0xE91+i,6);w(0xEB1+i,0x50);w(0xEC1+i,0) end
  w(0x010E,r(0x0104));p('CONTROLLED original loader scene1C camera0700; event15 entrance preparation')
 end
end,emu.callbackType.exec,0x7411,0x7411,emu.cpuType.snes,emu.memType.snesPrgRom)

local lastBattlePc=nil;local battleSince=0;local defeats=0
emu.addMemoryCallback(function()
 if not started or postBattle then return end
 local pc=r(0x1D20)+256*r(0x1D21)
 if pc>=0xB92F and pc<=0xB953 then
  if not battlePrepared and pc==0xB94B and r(0x122B)==1 and r(0x122D)==0 then
   battlePrepared=true
   -- ONE-TIME controlled starting stats, NOT defeated/inactive markers.
   -- Original attacks, KO, experience, rewards and event completion now run.
   w(0x104,200);w(0x10E,200)
   for i=4,6 do w(0x12A6+i,1) end
   postBattle=true;prepareEndWrites=writeCount;prepareEndFrame=n
   p('CONTROLLED battle-ready stats once; ALL preparation WRAM writes STOP HERE')
   p(string.format('PREPARATION_STOP f=%d writes=%d nativeVM=B94B enemyhp=1 playerhp=200',n,writeCount))
   checkpoint='battle-ready'
  end
  return
 end
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
local branchSeen={}
emu.addMemoryCallback(function()
 local pc=r(0x1D20)+256*r(0x1D21)
 if started and not postBattle and (pc==0xB69E or pc==0xB782) and not branchSeen[pc] then
  branchSeen[pc]=true;w(0x1BE4,0)
  p(string.format('CONTROLLED original preparatory branch stage0 pc=%04X',pc))
 end
end,emu.callbackType.exec,0x38F1B,0x38F1B,emu.cpuType.snes,emu.memType.snesPrgRom)
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
  if id>=0x151 and id<=0x154 and not checkpoints[id] then
   checkpoints[id]=true;checkpoint=string.format('msg-%04X',id)
  end
  if id==0x153 then p('REACHED original police/entry message0153 after real KO path') end
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
 if n%120==0 and battlePrepared then
  p(string.format('FIGHT f=%d phase=%02X/%02X playerhp=%d xp=%02X%02X targets=%02X/%02X/%02X hp=%d/%d/%d',n,r(0x122B),r(0x122D),r(0x10E),r(0x101),r(0x100),r(0xE01+4),r(0xE01+5),r(0xE01+6),r(0x12A6+4),r(0x12A6+5),r(0x12A6+6)))
 end
 if shots[n] then dump(tostring(n)) end
 if n>=maxf or ((os.getenv('PLAY_STOP_POLICE') or '')=='1' and checkpoints[0x153] and checkpoint==nil) then
  assert(battlePrepared and checkpoints[0x153], 'final KO/police checkpoint not reached')
  assert(writeCount==prepareEndWrites,'Lua wrote memory after final battle start')
  p(string.format('FIXTURE_PROOF finalBattle=true police0153=true preparationStopFrame=%d luaWritesAfterStop=%d; CONTROLLED, not natural story',prepareEndFrame,writeCount-prepareEndWrites))
  p(string.format('END vm=%d train=%d moving=%d postBattle=%s qTrainWrites=%d',cmds,stores,moving,tostring(postBattle),qTrainWrites));wantSave=true end
end,emu.eventType.endFrame)
