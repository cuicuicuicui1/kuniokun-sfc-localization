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
local targets={4,1,0,2,3,5,4};local phase=1;local startFrame=0;local commandFrame=nil;local commands={};local toggles={}
emu.addEventCallback(function()
 local key={a=false,b=false,x=false,y=false,up=false,down=false,left=false,right=false,start=false,select=false,l=false,r=false}
 if ready and phase<=#targets then
  if commandFrame then
   if n-commandFrame>80 then key.b=n%14<4 end
   if n-commandFrame>170 and r(0x314)<128 and r(0x373)==0 then phase=phase+1;startFrame=n;commandFrame=nil end
  elseif n-startFrame>15 then
   if r(0x314)<128 then
    if r(0x373)==0 then key.start=n%20<4 else key.a=n%14<4;key.b=n%14<4 end
   else
    local current=r(0x39A);local target=targets[phase]
    if current==target then key.y=n%14<4
    elseif current%3~=target%3 then key.right=n%14<3
    else key.down=n%14<3 end
   end
  elseif r(0x373)~=0 then key.a=n%14<4;key.b=n%14<4 end
 elseif ready then
  -- Native optimized L+R+X plus right adjusts actor type, not friendly fire.
  if (n>=2300 and n<2306) or (n>=2350 and n<2356) then key.l=true;key.r=true;key.x=true;key.right=true end
 end
 emu.setInput(key,0)
end,emu.eventType.inputPolled)
emu.addMemoryCallback(function()
 if phase<=#targets and not commandFrame then
  local command=r(0x368);if command>=128 then return end;commands[#commands+1]=command;commandFrame=n
  p(string.format('MENU_COMMAND phase=%d want=%d got=%d f=%d',phase,targets[phase],command,n))
  if command~=targets[phase] then p('WRONG_MENU_COMMAND');emu.stop(7);return end
 end
end,emu.callbackType.exec,0x1AB020,0x1AB020,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function(address,value)
 toggles[#toggles+1]=value;p(string.format('TOGGLE f=%d value=%02X',n,value))
end,emu.callbackType.write,0x70,0x70,emu.cpuType.snes,emu.memType.snesWorkRam)
emu.addEventCallback(function()
 if n>=maxf then
  local g=assert(io.open(out..'/menu-loop-results.json','w'));local a={};local b={}
  for _,v in ipairs(commands) do a[#a+1]=tostring(v) end
  for _,v in ipairs(toggles) do b[#b+1]=tostring(v) end
  g:write('{"commands":['..table.concat(a,',')..'],"toggle_values":['..table.concat(b,',')..'],"completed_phases":'..(phase-1)..'}');g:close()
  if #commands~=#targets or #toggles<2 then p('MENU_LOOP_INCOMPLETE');emu.stop(7);return end
 end
end,emu.eventType.endFrame)
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

local uiOverride=false
emu.addMemoryCallback(function()
 if not uiOverride then
  uiOverride=true
  local player=tonumber(os.getenv('UI_PLAYER') or '')
  local cond=tonumber(os.getenv('UI_CONDITION') or '')
  if player then emu.write(0x1BA6,player,mem) end
  if cond then emu.write(0x1EB+(player or r(0x1BA6)),cond,mem) end
  if player or cond then p('STATUS_RENDER_ENTRY one-time player/condition override; original menu call retained')
  else p('STATUS_RENDER_ENTRY observation only; no RAM writes') end
  local st=emu.getState()
  for k,v in pairs(st) do if k:lower():find('blank') or k:lower():find('brightness') then p(k..'='..tostring(v)) end end
 end
end,emu.callbackType.exec,0x1FBBB,0x1FBBB,emu.cpuType.snes,mem)

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

-- Controlled idle-state branch for the two friendly-fire command calls.
local toggleInputs=0
emu.addMemoryCallback(function()
 toggleInputs=toggleInputs+1
 emu.write(0x0E21,0,mem);emu.write(0x0E22,0,mem)
 p('CONTROLLED_IDLE_TOGGLE '..toggleInputs..'; original command/gating code retained')
end,emu.callbackType.exec,0x1AB058,0x1AB058,emu.cpuType.snes,emu.memType.snesPrgRom)
