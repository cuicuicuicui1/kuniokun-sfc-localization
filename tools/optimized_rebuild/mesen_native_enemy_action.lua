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
local n=0;local ready=false;local wantSave=false;local pendingCheckpoint=nil
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
local function xpos(i) return r(0xE81+i)+256*r(0xE91+i) end
local menuSeen=false
local menuAt=nil
local route={}
local routeKey=''
local routeFrom=0
local steer=0
local steerAt=tonumber(os.getenv('STEER_AT') or '0')
local steerUntil=tonumber(os.getenv('STEER_UNTIL') or '700')
emu.addEventCallback(function()
 local key={a=false,b=false,x=false,y=false,up=false,down=false,left=false,right=false,start=false,select=false,l=false,r=false}
 if ready then for _,e in ipairs(events) do if n>=e[1] and n<e[2] then for _,k in ipairs(e[3]) do assert(key[k]~=nil,'unknown input '..k);key[k]=true end end end end
 if ready and n>=steerAt and n<steerUntil then
  for k in pairs(key) do key[k]=false end
  local cursor=r(0x1F)
  if steer==0 then
   if (cursor&15)~=0 then key.left=n%12<4 elseif cursor~=0 then key.up=n%12<4 else steer=1;p('NAME type') end
  elseif steer==1 then
   if r(0x17)==0 then key.y=n%10<3 else steer=2;p('NAME to end') end
  elseif steer==2 then
   if cursor==0x8C then steer=3;p('NAME confirm')
   elseif (cursor&0xF0)==0x80 then key.right=n%12<4
   elseif cursor==0x7C then key.down=n%12<4
   elseif (cursor&0xF0)<0x80 then key.down=n%12<4 else key.up=n%12<4 end
  else key.y=n%10<3 end
 end
 if ready and n>=steerUntil and (os.getenv('AUTO_DIALOGUE') or '')=='1' and r(0x373)~=0 and r(0x314)<128 then
  key.a=n%20<4;key.b=n%20<4
 end
 if ready and (os.getenv('MAINLINE_FIGHT') or '')=='1' and r(0x373)==0
     and (r(0x122B)~=0 or r(0x122D)~=0) and r(0x314)<128 then
  local x=xpos(0);local y=r(0xEB1);local target=nil;local score=100000
  -- Original combat arrays have SEVEN actors; slots2..6 only. Civilians,
  -- allies, scripted NPCs, zero-HP and inactive/KO actors are NOT targets.
  for i=2,6 do
   local hp=r(0x12A6+i)+256*r(0x12AD+i)
   if r(0x122F+i)==1 and r(0xE01+i)>=128 and r(0xE01+i)~=0x82 and hp>0 then
    local dx=xpos(i)-x;local dy=r(0xEB1+i)-y
    local cost=math.abs(dx)+4*math.abs(dy)
    if cost<score then score=cost;target={i,dx,dy,hp} end
   end
  end
  if target then
   key.left=false;key.right=false;key.up=false;key.down=false;key.a=false;key.b=false;key.y=false
   local dx=target[2];local dy=target[3]
   if math.abs(dy)>3 then key.up=dy>0;key.down=dy<0 end
   if math.abs(dx)>14 then key.left=dx<0;key.right=dx>0 end
   if math.abs(dx)<35 and math.abs(dy)<=6 then
    key.left=dx<0;key.right=dx>0;key.y=n%10<4;key.b=n%30<4;key.a=n%64<3
   end
   if n%120==0 then p(string.format('FIGHT_INPUT f=%d enemy=%d membership=01 hp=%d delta=%d/%d playerHP=%d',n,target[1],target[4],dx,dy,r(0x10E))) end
  end
 end
 if ready and (os.getenv('AUTO_DOOR') or '')=='1' and r(0x900)==5 and r(0x373)==0 and r(0x314)<128 then
  local x=xpos(0);local target=tonumber(os.getenv('DOOR_X') or '444')
  key.left=x>target+3;key.right=x<target-3
  key.up=math.abs(x-target)<=6;key.down=false
  if n%120==0 then p(string.format('DOOR_INPUT f=%d x=%d y=%d map=%02X',n,x,r(0xEB1),r(0x900))) end
 end
 if (os.getenv('AUTO_MENU') or '')=='1' and n>3500 and not menuSeen and r(0x373)==0 then key.start=n%30<4 end
 if r(0x314)>=128 and not menuSeen then menuSeen=true;menuAt=n;p('MENU_OPEN '..n) end
 local active={} for _,k in ipairs({'a','b','x','y','l','r','up','down','left','right','start','select'}) do if key[k] then active[#active+1]=k end end
 local text=table.concat(active,',')
 if text~=routeKey then
  if routeKey~='' then route[#route+1]=tostring(routeFrom)..'-'..tostring(n)..':'..routeKey end
  routeFrom=n;routeKey=text
 end
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
 if pendingCheckpoint then
  local g=assert(io.open(out..'/'..tag..'-checkpoint-'..pendingCheckpoint..'.state','wb'));g:write(emu.createSavestate());g:close();pendingCheckpoint=nil
 end
 if wantSave then
  wantSave=false
  if routeKey~='' then route[#route+1]=tostring(routeFrom)..'-'..tostring(n)..':'..routeKey end
  local q=assert(io.open(out..'/actual-route.json','w'));q:write('{"frames":'..tostring(n)..',"input":"'..table.concat(route,';')..'","shots":[3200,4800,6200,8100,9000]}');q:close()
  local data=assert(emu.createSavestate());local g=assert(io.open(out..'/'..tag..'.state','wb'));g:write(data);g:close()
  p('SAVED frames='..n);log:close();emu.stop(0)
 end
end,emu.callbackType.exec,0x8000,0xFFFF,emu.cpuType.snes,mem)
local draw=0
emu.addMemoryCallback(function()
 draw=draw+1
 if (os.getenv('PLAY_TRACE') or '')=='1' then p(string.format('DRAW f=%d ix=%02X len=%02X code=%02X row=%02X col=%02X held=%02X/%02X edge=%02X/%02X',n,r(0x3E9),r(0x3E8),r(0x12),r(0x36E),r(0x36F),r(0x31A),r(0x31C),r(0x316),r(0x318))) end
end,emu.callbackType.exec,0x3FA30,0x3FA30,emu.cpuType.snes,mem)
emu.addEventCallback(function()
 if not ready then return end
 n=n+1
 if shots[n] then dump(tostring(n));pendingCheckpoint=tostring(n) end
 if n%300==0 then p(string.format('FRAME %d draws=%d held=%02X/%02X',n,draw,r(0x31A),r(0x31C))) end
 if n>=maxf then wantSave=true end
end,emu.eventType.endFrame)

local messageCaptured=false
emu.addMemoryCallback(function()
 if ready and not messageCaptured and n>steerUntil then
  messageCaptured=true
  local g=assert(io.open(out..'/message-ready.state','wb'));g:write(emu.createSavestate());g:close()
  p(string.format('MESSAGE_READY f=%d id=%02X%02X map=%02X',n,r(0x34B),r(0x34A),r(0x900)))
 end
end,emu.callbackType.exec,0x1EB07,0x1EB07,emu.cpuType.snes,emu.memType.snesPrgRom)

local menuCaptured=false
emu.addMemoryCallback(function()
 if ready and menuAt and n>menuAt+30 and not menuCaptured then
  menuCaptured=true;dump('menu')
  local g=assert(io.open(out..'/menu-ready.state','wb'));g:write(emu.createSavestate());g:close()
  p('MENU_READY '..n)
 end
end,emu.callbackType.exec,0x7539,0x7539,emu.cpuType.snes,emu.memType.snesPrgRom)

local visits={}
local oldBankExec=0
emu.addMemoryCallback(function()
 local st=emu.getState();local cpuBank=st['cpu.k']
 if cpuBank==0x20 or cpuBank==0x22 or cpuBank==0x23 then oldBankExec=oldBankExec+1 end
end,emu.callbackType.exec,0x208000,0x23FFFF,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 local id=r(0x34A)+256*r(0x34B);local speaker=r(0x34C)+256*r(0x34D)
 visits[id]=(visits[id] or 0)+1
 p(string.format('MSG_ENTRY f=%d id=%04X speaker=%04X sourceCondition=%02X actorKind=%02X/flag=%02X',n,id,speaker,r(0x373),r(0xF01+2),r(0x1490+2)))
end,emu.callbackType.exec,0x3EB07,0x3EB07,emu.cpuType.snes,mem)

-- Physical WRAM ownership probe for the new font namespace byte.
local laneWrites=0
emu.addMemoryCallback(function(address,value)
 local st=emu.getState();laneWrites=laneWrites+1
 if n>2200 and st['cpu.k']~=0x30 and not (st['cpu.k']==3 and st['cpu.pc']==0xE9A0 and value==0) then
  p(string.format('LANE_UNEXPECTED f=%d cpu=%02X:%04X value=%02X',n,st['cpu.k'],st['cpu.pc'],value));emu.stop(6)
 end
end,emu.callbackType.write,0x3E5,0x3E5,emu.cpuType.snes,assert(emu.memType.snesWorkRam))
local namespaceWrites=0
emu.addMemoryCallback(function(address,value)
 local st=emu.getState();local bank=st['cpu.k'];local pc=st['cpu.pc']
 namespaceWrites=namespaceWrites+1
 if n>2450 and bank~=0x30 and bank~=0x38 and not (bank==3 and pc==0xE9A0 and value==0) then
  p(string.format('FIELD_UNEXPECTED f=%d cpu=%02X:%04X value=%02X',n,bank,pc,value or 0))
  emu.stop(5);return
 end
end,emu.callbackType.write,0x3E6,0x3E6,emu.cpuType.snes,assert(emu.memType.snesWorkRam))
emu.addEventCallback(function()
 if ready and n>=maxf then p('FIELD_WRITES_OK '..namespaceWrites..' lane='..laneWrites..' nativeBankExec='..oldBankExec) end
end,emu.eventType.endFrame)

local crowdMax=0;local livingMax=0;local observedMaps={};local framesCrowd=0;local boundaryHits=0;local trainChecks=0;local npcIDs={};local uploads=0
local function actorSummary()
 local a={};local count=0;local living=0
 for i=0,6 do
  if r(0xE01+i)>=128 then
   count=count+1;if r(0x122F+i)~=0 then living=living+1 end
   local id=r(0x124D+i)+256*r(0x1246+i)
   if i>=2 then npcIDs[id]=(npcIDs[id] or 0)+1 end
   a[#a+1]=string.format('%d:%04X/k%02X/g%02X/hp%d',i,id,r(0xF01+i),r(0x122F+i),r(0x12A6+i)+256*r(0x12AD+i))
  end
 end
 return count,living,table.concat(a,' ')
end
emu.addMemoryCallback(function()
 local st=emu.getState()
 if st['cpu.k']==0x30 or st['cpu.k']==0x3E then
  boundaryHits=boundaryHits+1;p(string.format('PATCH_QUEUE_BOUNDARY_WRITE f=%d cpu=%02X:%04X',n,st['cpu.k'],st['cpu.pc']))
 end
end,emu.callbackType.write,0xC00,0xC0F,emu.cpuType.snes,emu.memType.snesWorkRam)
local neighborCorruptions=0;local pendingQueue=nil
emu.addMemoryCallback(function()
 if pendingQueue then return end
 pendingQueue={r(0x9E0),r(0x9E1),r(0x9DE)}
end,emu.callbackType.exec,0x1FA30,0x1FA30,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()
 if pendingQueue then
  trainChecks=trainChecks+1
  if pendingQueue[1]~=r(0x9E0) or pendingQueue[2]~=r(0x9E1) or pendingQueue[3]~=r(0x9DE) then
   neighborCorruptions=neighborCorruptions+1;p('DRAWER_CHANGED_TRAIN_OR_QUEUE_NEIGHBOR');pendingQueue=nil;emu.stop(8);return
  end
  pendingQueue=nil
 end
end,emu.callbackType.exec,0x1FA7D,0x1FA7D,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addEventCallback(function()
 if not ready then return end
 local count,living,actors=actorSummary()
 if count>crowdMax then crowdMax=count;p('CROWD_MAX '..count..' f='..n..' '..actors) end
 livingMax=math.max(livingMax,living)
 if count>=5 then framesCrowd=framesCrowd+1 end
 observedMaps[r(0x900)]=(observedMaps[r(0x900)] or 0)+1
 if n%600==0 then p(string.format('CROWD f=%d active=%d livingGroup=%d map=%02X queue=%d/%d npc=%s',n,count,living,r(0x900),r(0x9DD),r(0x9DF),actors)) end
 if n>=maxf then
  local maps={};local ids={}
  for k,v in pairs(observedMaps) do maps[#maps+1]=string.format('"%02X":%d',k,v) end
  for k,v in pairs(npcIDs) do ids[#ids+1]=string.format('"%04X":%d',k,v) end
  local f=assert(io.open(out..'/crowd-observation.json','w'));f:write('{"max_active_actors":'..crowdMax..',"max_group_members":'..livingMax..',"frames_at_least_five":'..framesCrowd..',"patch_writes_queue_boundary":'..boundaryHits..',"drawer_neighbor_checks":'..trainChecks..',"drawer_neighbor_corruptions":'..neighborCorruptions..',"maps":{'..table.concat(maps,',')..'},"npc_records":{'..table.concat(ids,',')..'}}');f:close()
 end
end,emu.eventType.endFrame)

local enemyReplaced=false
local enemyRecord=tonumber(os.getenv('ENEMY_RECORD') or '11F',16)
assert(enemyRecord>=0 and enemyRecord<514)
emu.addMemoryCallback(function()
 if enemyReplaced then return end
 local st=emu.getState();local slot=st['cpu.x'];local source=r(0x124D+slot)+256*r(0x1246+slot)
 if slot>=2 and slot<=6 and source>=0x18 and source<=0x1c then
  enemyReplaced=true
  emu.write(0x24,enemyRecord&255,mem);emu.write(0x25,enemyRecord>>8,mem)
  emu.write(0x124D+slot,enemyRecord&255,mem);emu.write(0x1246+slot,enemyRecord>>8,mem)
  p(string.format('CONTROLLED_ENEMY_RECORD f=%d slot=%d before=%04X after=%04X; original actor initializer retained, no HP/PC/story writes',n,slot,source,enemyRecord))
 end
end,emu.callbackType.exec,0x3DBBA,0x3DBBA,emu.cpuType.snes,emu.memType.snesPrgRom)
for _,addr in ipairs({0x100220,0x100250,0x100280}) do
 emu.addMemoryCallback(function()
  local st=emu.getState();local slot=st['cpu.x'];local id=r(0x124D+slot)+256*r(0x1246+slot)
  p(string.format('OPT_COMBAT_CALL f=%d cpu=%02X:%04X slot=%d actor=%04X kind=%02X flag=%02X',n,st['cpu.k'],st['cpu.pc'],slot,id,r(0xF01+slot),r(0x1490+slot)))
 end,emu.callbackType.exec,addr,addr,emu.cpuType.snes,emu.memType.snesPrgRom)

end -- native combat probe loop
local actionTriggered=false
emu.addMemoryCallback(function()
 if enemyReplaced and not actionTriggered and n>=300 and r(0x373)==0 and r(0x122F+2)==1 and (r(0x1490+2)&128)~=0 then
  actionTriggered=true
  emu.write(0x1348,2,mem);emu.write(0x149F,1,mem)
  p(string.format('CONTROLLED_TAUNT_SELECTOR f=%d slot=2; native combat dispatch and real actor preserved; no PC/ROM/HP/story writes',n))
 end
end,emu.callbackType.exec,0x3F0B0,0x3F0B0,emu.cpuType.snes,emu.memType.snesPrgRom)
