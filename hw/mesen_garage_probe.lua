-- Kunio-kun underground-garage INPUT-ONLY replay probe (2026-10-02).
-- Requires a checkpoint for the SAME ROM. Load/save only in isolated outputs.
-- No WRAM/SRAM/ROM writes, CPU-PC changes, enemy defeat or event-flag injection.
-- Native bank02/04/07 addresses below belong to this game, not generic SNES.
-- tools/run_mesen_play.py sets PLAY_*; optional switches MUST be explicit:
--   AUTO_DIALOGUE=1: A pulses while messages are active.
--   GARAGE_ENTER=1: ordinary UP/DOWN/RIGHT inputs after event15 finishes.
--   GARAGE_EXPECT_ENTRY=1: require native gate95 acceptance AND map4C entry.
-- None of these switches grants natural-story/full-game acceptance.
local out=assert(os.getenv('PLAY_OUT'))
local tag=assert(os.getenv('PLAY_TAG'))
local state=assert(os.getenv('PLAY_STATE'))
assert(state~='', 'same-ROM checkpoint required; cold boot is not this probe')
assert((os.getenv('PLAY_SRAM') or '')=='', 'do not seed SRAM during a replay')
local maxf=tonumber(os.getenv('PLAY_FRAMES') or '1200')
assert(maxf>0)
local mem=emu.memType.snesMemory
local prg=emu.memType.snesPrgRom
local logfile=assert(io.open(out..'/'..tag..'.log','w'))
local function p(s) logfile:write(s..'\n');logfile:flush() end
local function r(a) return emu.read(a,mem)&255 end
local function r16(a) return r(a)+256*r(a+1) end
local function xpos(i) return r(0xE81+i)+256*r(0xE91+i) end
local function objects()
 local a={} for i=0,15 do a[#a+1]=string.format('%02X',r(0x8C6+i)) end
 return table.concat(a,',')
end
local function actors()
 local a={}
 for i=0,6 do
  a[#a+1]=string.format('%d:%02X,state%02X,x%04X,y%02X,hp%d,enemy%02X,name%02X,npcRole%02X,gateControl%02X,moveFlags%02X',
   i,r(0xE01+i),r(0xE11+i),xpos(i),r(0xEB1+i),
   i<2 and r(0x10E+i) or (r(0x12A6+i)+256*r(0x12AD+i)),
   r(0x122F+i),r(0x124D+i),r(0x1331+i),r(0x303+i),r(0x1D2C+i))
 end
 return table.concat(a,' ')
end
local n=0
local ready=false
local ending=false
local lastmap=-1
local lastvm=-1
local nativeCalls=0
local gateAccepted=0
local entered=false
local entryFrame=nil
local events={}
for lo,hi,keys in (os.getenv('PLAY_INPUT') or ''):gmatch('(%d+)%-(%d+):([%w,+]+)') do
 local buttons={} for k in keys:gmatch('%w+') do buttons[#buttons+1]=k end
 events[#events+1]={tonumber(lo),tonumber(hi),buttons}
end
local shots={}
for f in (os.getenv('PLAY_SHOTS') or '30'):gmatch('%d+') do shots[tonumber(f)]=true end
shots[maxf]=true
local function dump(label)
 local g=assert(io.open(out..'/'..tag..'-'..label..'.png','wb'))
 g:write(emu.takeScreenshot());g:close()
 for _,spec in ipairs({{'ram',mem,0x7E0000,0x20000},
                       {'vram',emu.memType.snesVideoRam,0,0x10000}}) do
  g=assert(io.open(out..'/'..tag..'-'..label..'.'..spec[1],'wb'))
  local a={} for i=0,spec[4]-1 do a[#a+1]=string.char(emu.read(spec[3]+i,spec[2])&255) end
  g:write(table.concat(a));g:close()
 end
 p('SHOT '..label)
end
local function status(label)
 local s=emu.getState()
 p(string.format('%s f=%d map=%02X camera=%04X event=%02X/%02X vm=04:%04X wait=%02X/%02X/%02X ext=%02X/%02X fight=%02X/%02X spawn=%02X control=%02X/%02X mode=%02X animation=%02X/%02X step=%02X message=%02X/%02X pending=%02X/%02X pos=%04X/%02X cpu=%02X:%04X blockers=[%s] actors=[%s]',
  label,n,r(0x900),r16(0x903),r(0x1D22),r(0x1D23),r16(0x1D20),
  r(0x1D25),r(0x1D26),r(0x1D27),r(0x1DA5),r(0x1DA6),
  r(0x122B),r(0x122D),r(0x8D7),r(0x303),r(0x304),r(0x31E),
  r(0x461),r(0x462),r(0x45F),r(0x373),r(0x374),r(0x9DD),r(0x9DF),
  xpos(0),r(0xEB1),s['cpu.k'],s['cpu.pc'],objects(),actors()))
end
emu.addEventCallback(function()
 local key={a=false,b=false,x=false,y=false,up=false,down=false,left=false,
            right=false,start=false,select=false,l=false,r=false}
 if ready then
  for _,e in ipairs(events) do
   if n>=e[1] and n<e[2] then
    for _,k in ipairs(e[3]) do assert(key[k]~=nil,'unknown input '..k);key[k]=true end
   end
  end
  if (os.getenv('AUTO_DIALOGUE') or '')=='1' and r(0x373)~=0 and n%30<3 then key.a=true end
  if (os.getenv('GARAGE_ENTER') or '')=='1' and r(0x900)==0x4B and r(0x1D23)==0x97
     and r(0x122B)==0 and r(0x122D)==0 and r(0x373)==0 then
   local y=r(0xEB1)
   -- Ordinary positioning inside the ORIGINAL gate's ground-coordinate range.
   if y<0x4C then key.up=true elseif y>0x50 then key.down=true else key.right=true end
  end
 end
 emu.setInput(key,0)
 local actual=emu.getInput(0)
 for k,v in pairs(key) do assert(actual[k]==v,'input override failed: '..k) end
end,emu.eventType.inputPolled)
-- Observe physical PRG addresses so bank aliases do not silently miss callbacks.
for _,pc in ipairs({0xF4C2,0xF9A2,0xF737,0xF8CB}) do
 local offset=0x10000+(pc&0x7FFF)
 emu.addMemoryCallback(function()
  if not ready then return end
  nativeCalls=nativeCalls+1
  if pc==0xF8CB and r(0x900)==0x4B and r(0x457)==0x4C then
   gateAccepted=gateAccepted+1
   p(string.format('GARAGE_GATE_ACCEPTED f=%d blocker=%02X animation=%02X/%02X list=[%s]',
    n,r(0x455),r(0x461),r(0x462),objects()))
  end
  if (pc==0xF9A2 or pc==0xF737) and r(0x900)==0x4B and n%30==0 then
   p(string.format('GATE f=%d pc=02:%04X ptr=%04X kind=%02X blocker=%02X target=%02X shape=%02X bounds=%02X/%02X/%02X/%02X pos=%04X/%02X controls=%02X/%02X list=[%s]',
    n,pc,r16(0x24),r(0x454),r(0x455),r(0x457),r(0x45A),
    r(0x45B),r(0x45C),r(0x45D),r(0x45E),xpos(0),r(0xEB1),r(0x303),r(0x304),objects()))
  end
 end,emu.callbackType.exec,offset,offset,emu.cpuType.snes,prg)
end
local vmoffset=0x38000+(0x8F1B&0x7FFF)
emu.addMemoryCallback(function()
 if not ready then return end
 local pc=r16(0x1D20)
 if pc~=lastvm then
  lastvm=pc
  p(string.format('VM f=%d pc=04:%04X op=%02X event=%02X doors=%02X/%02X list=[%s]',
   n,pc,r(0x40000+pc),r(0x1D23),r(0x14AE),r(0x14AF),objects()))
 end
end,emu.callbackType.exec,vmoffset,vmoffset,emu.cpuType.snes,prg)
local msgoffset=0x18000+(0xEB07&0x7FFF)
emu.addMemoryCallback(function()
 if ready then p(string.format('MESSAGE f=%d id=%04X speaker=%04X',n,r16(0x34A),r16(0x34C))) end
end,emu.callbackType.exec,msgoffset,msgoffset,emu.cpuType.snes,prg)
-- Load once at the cold-reset instruction. Save only at the ORIGINAL main
-- loop, avoiding a persistent all-instruction lifecycle callback.
emu.addMemoryCallback(function()
 if ready then return end
 ready=true
 local g=assert(io.open(state,'rb'));local data=g:read('*a');g:close()
 assert(emu.loadSavestate(data),'loadSavestate failed')
 p('LOADED '..state);p('SCOPE input-only replay; no memory/PC/event/defeat injection')
end,emu.callbackType.exec,0x3D36,0x3D36,emu.cpuType.snes,prg)
emu.addMemoryCallback(function()
 if not ready then return end
 if ending then
  ending=false
  local data=assert(emu.createSavestate())
  local g=assert(io.open(out..'/'..tag..'.state','wb'));g:write(data);g:close()
  local expect=(os.getenv('GARAGE_EXPECT_ENTRY') or '')=='1'
  local pass=entered and gateAccepted>0
  p(string.format('SCENE_PROOF entered4C=%s nativeGateAccepted=%d nativeCalls=%d expectedEntry=%s result=%s',
   tostring(entered),gateAccepted,nativeCalls,tostring(expect),expect and (pass and 'PASS' or 'FAIL') or 'INFO'))
  p('SAVED frames='..n);logfile:close();emu.stop(expect and not pass and 1 or 0)
 end
end,emu.callbackType.exec,0x7333,0x7333,emu.cpuType.snes,prg)
-- $00:F333 is the original common frame-wait RETURN, reached by the Start
-- overlay as well as normal gameplay. $00:F203 is bypassed while menus are
-- open; using only that boundary made completed menu captures time out.
emu.addEventCallback(function()
 if not ready then return end
 n=n+1
 if n%120==0 or r(0x900)~=lastmap then status('GAME');lastmap=r(0x900) end
 if r(0x900)==0x4C and gateAccepted>0 and not entered then
  entered=true;entryFrame=n;p('ENTERED map=4C f='..n..'; native garage gate already accepted')
 end
 if entryFrame and n==entryFrame+120 then dump('entered-4C') end
 if shots[n] then dump(tostring(n)) end
 if n>=maxf then status('RESULT');ending=true end
end,emu.eventType.endFrame)

-- Companion-aware ORIGINAL consumers. The presence of a friendly NPC alone
-- is not a failure: battle membership, cinematic completion, and portal
-- readiness are separate state machines. Read all seven slots, never clear
-- one to make an experiment pass.
local npcWaitKey=''
local function npcWait(label)
 if not ready or r(0x900)~=0x4B then return end
 local waiting={}
 for i=0,6 do
  if r(0xE01+i)>=128 and (r(0x1D2C+i)&0xE0)~=0 then
   waiting[#waiting+1]=string.format('%d:role%02X,enemy%02X,move%02X,pos%04X/%02X,target%04X/%04X',
    i,r(0x1331+i),r(0x122F+i),r(0x1D2C+i),xpos(i),r(0xEB1+i),
    r(0x1D3A+i)+256*r(0x1D41+i),r(0x1D48+i)+256*r(0x1D4F+i))
  end
 end
 local key=label..':'..r16(0x1D20)..':'..table.concat(waiting,' ')
 if key~=npcWaitKey then npcWaitKey=key;p(string.format('NPC_WAIT f=%d kind=%s vm=%04X slots=[%s]',n,label,r16(0x1D20),table.concat(waiting,' '))) end
end
emu.addMemoryCallback(function() npcWait('original-all-actor-move-wait') end,
 emu.callbackType.exec,0x38E07,0x38E07,emu.cpuType.snes,prg)
local blockedNpcKey=''
emu.addMemoryCallback(function()
 if not ready or r(0x900)~=0x4B then return end
 local st=emu.getState();local i=st['cpu.x']
 assert(i>=2 and i<7, 'original companion gate index outside actor slots')
 local key=i..':'..r(0x303+i)..':'..xpos(i)..':'..r(0xEB1+i)
 if key~=blockedNpcKey then
  blockedNpcKey=key
  p(string.format('NPC_GATE_WAIT f=%d actor=%d npcRole=%02X combatMembership=%02X control=%02X pos=%04X/%02X; original02:F69C requires companion ready bit10',
   n,i,r(0x1331+i),r(0x122F+i),r(0x303+i),xpos(i),r(0xEB1+i)))
 end
end,emu.callbackType.exec,0x176B6,0x176B6,emu.cpuType.snes,prg)

-- Observe the actual original menu return; zero hits is NOT ABI acceptance.
-- F703 loads the session byte before the F706 hook; F70B is the next native
-- instruction. The localization must preserve hidden accumulator B and replay
-- AND #EF / STA $0374, changing N/Z exactly as the original AND does.
local menuEntry=nil;local menuCalls=0;local menuBad=0;local menuReported=false
emu.addMemoryCallback(function()
 if not ready then return end
 local st=emu.getState()
 assert((st['cpu.ps']&0x30)==0x30,'native F706 M/X contract changed')
 menuEntry={a=st['cpu.a'],sp=st['cpu.sp'],ps=st['cpu.ps'],session=r(0x374),pending=r(0xBFB)}
 menuCalls=menuCalls+1
end,emu.callbackType.exec,0x1F706,0x1F706,emu.cpuType.snes,prg)
emu.addMemoryCallback(function()
 if not ready or not menuEntry then return end
 local st=emu.getState();local expected=menuEntry.a&0xFFEF;local low=expected&255
 local flags=(menuEntry.ps&0x7D)|(low&0x80)|(low==0 and 2 or 0)
 local bad=st['cpu.a']~=expected or r(0x374)~=low or st['cpu.sp']~=menuEntry.sp or st['cpu.ps']~=flags
 if bad then menuBad=menuBad+1 end
 if bad or menuCalls<=10 then
  p(string.format('NATIVE_MENU_ABI f=%d A=%04X resultA=%04X expectedA=%04X session=%02X/%02X pending=%02X stack=%04X/%04X P=%02X/%02X expectedP=%02X result=%s',
   n,menuEntry.a,st['cpu.a'],expected,menuEntry.session,r(0x374),menuEntry.pending,menuEntry.sp,st['cpu.sp'],menuEntry.ps,st['cpu.ps'],flags,bad and 'FAIL' or 'PASS'))
 end
 menuEntry=nil
end,emu.callbackType.exec,0x1F70B,0x1F70B,emu.cpuType.snes,prg)
emu.addEventCallback(function()
 if n>=maxf and not menuReported then
  menuReported=true;p(string.format('NATIVE_MENU_ABI_PROOF calls=%d mismatches=%d result=%s',menuCalls,menuBad,menuCalls==0 and 'UNEXERCISED' or (menuBad==0 and 'PASS' or 'FAIL')))
 end
end,emu.eventType.endFrame)
