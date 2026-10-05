-- CONTROLLED typography only: select existing VM message opcode and args in WRAM.
-- Uses original EB07/EB68/EB9E loaders; never writes ROM/PPU/fonts/upload queues.
-- Not natural item acquisition, location travel or full quest progression.
-- Isolated same-ROM state or cold boot; never edits player saves/settings.
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
emu.addEventCallback(function()
 local key={a=false,b=false,x=false,y=false,up=false,down=false,left=false,right=false,start=false,select=false,l=false,r=false}
 if ready then for _,e in ipairs(events) do if n>=e[1] and n<e[2] then for _,k in ipairs(e[3]) do assert(key[k]~=nil,'unknown input '..k);key[k]=true end end end end
 if ready and r(0x373)~=0 and n%60<3 then key.a=true end
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

-- Typography fixture only. Select existing VM opcode30 at04:A3BA to enter
-- ORIGINAL EB07/EB68/EB9E macro loader. No ROM, PPU, glyph or queue writes.
-- Script PC selection is a controlled entry, NOT a natural quest test.
local physical=emu.memType.snesWorkRam
local schedule={{80,598,17,0},{750,1,1,0},{1000,5,1,6},{1700,5,17,6},{2400,5,7,6},{3150,639,1,0,1},{3750,639,1,0,9},{4300,639,1,0,24},{4900,5,1,6},{5500,5,17,6},{6100,639,1,0,30},{6800,5,7,6}}
local nextcase=1;local requested=nil;local count=0
local function w(a,v) emu.write(a,v&255,mem) end
local function w16(a,v) w(a,v);w(a+1,v>>8) end
emu.addMemoryCallback(function()
 if ready and n>=40 then
  -- Isolate original player/dialogue context from opening quest AI.
  w(0x1D22,0);w(0x1D23,0);w(0x08D7,0)
 end
 if ready and nextcase<=#schedule and n>=schedule[nextcase][1] then
  local spec=schedule[nextcase];requested=spec;nextcase=nextcase+1
  w(0x1D23,0x88);w16(0x1D20,0xA3BA)
  for _,a in ipairs({0x1D25,0x1D26,0x1D27,0x1DA5,0x1DA6,0x1DA7,0x1DA8}) do w(a,0) end
  w(0x373,0);w(0x374,0)
  p(string.format('CONTROLLED existing VM message opcode case=%d frame=%d requested message=%04X item=%d',nextcase-1,n,spec[2],spec[3]))
 end
end,emu.callbackType.exec,0xF203,0xF203,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 if requested then
  local spec=requested;requested=nil;count=count+1
  w16(0x34A,spec[2]);w16(0x34C,0x0200);w16(0x34E,0x0200)
  w(0x356,spec[3]);w(0x35A,spec[4]);w(0x35C,spec[5] or 1);w(0x35D,21);w(0x35E,0)
  w(0x1D23,0)
  p(string.format('ORIGINAL EB07 case=%d id=%04X item=%d status=%d',count,spec[2],spec[3],spec[4]))
 end
end,emu.callbackType.exec,0x3EB07,0x3EB07,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 p(string.format('ORIGINAL LOADER f=%d source=%04X item=%d buffer=%02X/%02X row=%02X col=%02X',n,r(0x36A)+256*r(0x36B),r(0x356),r(0x3E9),r(0x3E8),r(0x36E),r(0x36F)))
end,emu.callbackType.exec,0x3EB9E,0x3EB9E,emu.cpuType.snes,mem)
local itemCount=0
emu.addMemoryCallback(function()
 if r(0x12)==0xDE then
  itemCount=itemCount+1
  if itemCount<40 then p(string.format('DE f=%d index=%02X ident=%02X col=%02X row=%02X',n,r(0x3E9),r(0x3EA+r(0x3E9)+1),r(0x36F),r(0x36E))) end
 end
end,emu.callbackType.exec,0x3FA30,0x3FA30,emu.cpuType.snes,mem)
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
 if n>=maxf then assert(count==#schedule and itemCount>=12,'fixture did not exercise real names/messages');p('TYPOGRAPHY count='..count..' DE='..itemCount);wantSave=true end
end,emu.eventType.endFrame)
