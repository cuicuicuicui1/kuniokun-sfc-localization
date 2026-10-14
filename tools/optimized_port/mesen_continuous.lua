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
 if ready and n>=steerUntil and (os.getenv('AUTO_DIALOGUE') or '')=='1' and r(0x373)~=0 then
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
 if shots[n] then dump(tostring(n)) end
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
 if cpuBank==0x20 or cpuBank==0x22 or cpuBank==0x23 then oldBankExec=oldBankExec+1;p('UNRELOCATED_CPU_EXEC '..string.format('%02X:%04X',cpuBank,st['cpu.pc'])) end
end,emu.callbackType.exec,0x208000,0x23FFFF,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 local id=r(0x34A)+256*r(0x34B);local speaker=r(0x34C)+256*r(0x34D)
 visits[id]=(visits[id] or 0)+1
 p(string.format('MSG_ENTRY f=%d id=%04X speaker=%04X sourceCondition=%02X actorKind=%02X/flag=%02X',n,id,speaker,r(0x373),r(0xF01+2),r(0x1490+2)))
end,emu.callbackType.exec,0x3EB07,0x3EB07,emu.cpuType.snes,mem)

-- Physical WRAM ownership probe for the new font namespace byte.
local namespaceWrites=0
emu.addMemoryCallback(function(address,value)
 local st=emu.getState();local bank=st['cpu.k'];local pc=st['cpu.pc']
 namespaceWrites=namespaceWrites+1
 if n>2450 and bank~=0x38 and not (bank==3 and pc==0xE9A0 and value==0) then
  p(string.format('FIELD_UNEXPECTED f=%d cpu=%02X:%04X value=%02X',n,bank,pc,value or 0))
  emu.stop(5);return
 end
end,emu.callbackType.write,0x3E6,0x3E6,emu.cpuType.snes,assert(emu.memType.snesWorkRam))
emu.addEventCallback(function()
 if ready and n>=maxf then p('FIELD_WRITES_OK '..namespaceWrites) end
end,emu.eventType.endFrame)

-- Continuous original gameplay calls: one cold boot, no restore between text.
local sequence={0x032,0x31C,0x31D,0x032,0x31E,0x348,0x032,0x1F6,0x338,0x032,0x337}
local ix=0;local clears=0;local body=0;local pendingScreenshot=nil
local report={}
emu.addMemoryCallback(function()
 if n<2450 or ix>=#sequence then return end
 ix=ix+1;local id=sequence[ix]
 report[#report+1]=string.format('{"id":"%03X","frame":%d,"previous_namespace":%d}',id,n,r(0x3E6)&1)
 emu.write(0x34A,id&255,mem);emu.write(0x34B,id>>8,mem)
 emu.write(0x35D,0x4A,mem);emu.write(0x35E,0x3C,mem)
 p(string.format('CONTINUOUS_NATIVE_CALL index=%d id=%03X previous=%d',ix,id,r(0x3E6)&1))
 pendingScreenshot={n+65,ix,id}
end,emu.callbackType.exec,0x1EB07,0x1EB07,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()
 clears=clears+1
 p(string.format('NATIVE_CLEAR f=%d id=%04X',n,r(0x34A)+256*r(0x34B)))
end,emu.callbackType.exec,0x1FCC8,0x1FCC8,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addEventCallback(function()
 if pendingScreenshot and n>=pendingScreenshot[1] then
  local g=assert(io.open(out..'/continuous-'..pendingScreenshot[2]..'.png','wb'));g:write(emu.takeScreenshot());g:close();pendingScreenshot=nil
 end
 if n>=maxf then
  if ix~=#sequence then p("CONTINUOUS_INCOMPLETE "..ix);emu.stop(6);return end
  local g=assert(io.open(out..'/continuous-results.json','w'));g:write('{"entries":['..table.concat(report,',')..'],"native_clear_calls":'..clears..',"scope":"one cold boot, original calls with message/common parameters controlled, no state reload, no PC/ROM/story writes"}');g:close()
 end
end,emu.eventType.endFrame)
