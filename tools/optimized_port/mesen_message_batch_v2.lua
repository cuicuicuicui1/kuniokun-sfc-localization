-- Same-ROM cold checkpoint, controlled message/speaker parameters only.
-- Each case uses the original message call and renderer; no injected PC/ROM.
local out=assert(os.getenv('PLAY_OUT'));local tag=assert(os.getenv('PLAY_TAG'))
local maxf=tonumber(os.getenv('PLAY_FRAMES'));local mem=emu.memType.snesMemory
local f=assert(io.open(os.getenv('PLAY_STATE'),'rb'));local checkpoint=f:read('*a');f:close()
local log=assert(io.open(out..'/'..tag..'.log','w'))
local function p(s)log:write(s..'\n');log:flush()end
local function r(a)return emu.read(a,mem)&255 end
local function w(a,v)emu.write(a,v&255,mem)end
local function word(a)return r(a)+256*r(a+1)end
local cases={
{id=0x301,speaker=0x0001,capture=true},
{id=0x302,speaker=0x011F,capture=false},
{id=0x303,speaker=0x0125,capture=false},
{id=0x304,speaker=0x01D3,capture=false},
{id=0x305,speaker=0x0201,capture=false},
{id=0x306,speaker=0x0001,capture=false},
{id=0x307,speaker=0x011F,capture=false},
{id=0x308,speaker=0x0125,capture=false},
{id=0x309,speaker=0x01D3,capture=false},
{id=0x30A,speaker=0x0201,capture=false},
{id=0x30B,speaker=0x0001,capture=false},
{id=0x30C,speaker=0x011F,capture=true},
{id=0x30D,speaker=0x0125,capture=false},
{id=0x30E,speaker=0x01D3,capture=false},
{id=0x30F,speaker=0x0201,capture=false},
{id=0x310,speaker=0x0001,capture=true},
{id=0x311,speaker=0x011F,capture=false},
{id=0x312,speaker=0x0125,capture=false},
{id=0x313,speaker=0x01D3,capture=false},
{id=0x314,speaker=0x0201,capture=false},
{id=0x315,speaker=0x0001,capture=false},
{id=0x316,speaker=0x011F,capture=false},
{id=0x317,speaker=0x0125,capture=false},
{id=0x318,speaker=0x01D3,capture=false},
{id=0x319,speaker=0x0201,capture=false},
{id=0x31A,speaker=0x0001,capture=false},
{id=0x31B,speaker=0x011F,capture=false},
{id=0x31C,speaker=0x0125,capture=false},
{id=0x31D,speaker=0x01D3,capture=true},
{id=0x31E,speaker=0x0201,capture=true},
{id=0x31F,speaker=0x0001,capture=false},
{id=0x320,speaker=0x011F,capture=false},
{id=0x321,speaker=0x0125,capture=false},
{id=0x322,speaker=0x01D3,capture=false},
{id=0x323,speaker=0x0201,capture=false},
{id=0x324,speaker=0x0001,capture=false},
{id=0x325,speaker=0x011F,capture=false},
{id=0x326,speaker=0x0125,capture=false},
{id=0x327,speaker=0x01D3,capture=false},
{id=0x328,speaker=0x0201,capture=false},
{id=0x329,speaker=0x0001,capture=false},
{id=0x32A,speaker=0x011F,capture=false},
{id=0x32B,speaker=0x0125,capture=false},
{id=0x32C,speaker=0x01D3,capture=false},
{id=0x32D,speaker=0x0201,capture=false},
{id=0x32E,speaker=0x0001,capture=false},
{id=0x32F,speaker=0x011F,capture=false},
{id=0x330,speaker=0x0125,capture=false},
{id=0x331,speaker=0x01D3,capture=false},
{id=0x332,speaker=0x0201,capture=false},
{id=0x333,speaker=0x0001,capture=false},
{id=0x334,speaker=0x011F,capture=false},
{id=0x335,speaker=0x0125,capture=false},
{id=0x336,speaker=0x01D3,capture=true},
{id=0x337,speaker=0x0201,capture=true},
{id=0x338,speaker=0x0001,capture=true},
{id=0x339,speaker=0x011F,capture=false},
{id=0x33A,speaker=0x0125,capture=true},
{id=0x33B,speaker=0x01D3,capture=false},
{id=0x33C,speaker=0x0201,capture=false},
{id=0x33D,speaker=0x0001,capture=true},
{id=0x33E,speaker=0x011F,capture=false},
{id=0x33F,speaker=0x0125,capture=false},
{id=0x340,speaker=0x01D3,capture=false},
{id=0x341,speaker=0x0201,capture=false},
{id=0x342,speaker=0x0001,capture=false},
{id=0x343,speaker=0x011F,capture=false},
{id=0x344,speaker=0x0125,capture=false},
{id=0x345,speaker=0x01D3,capture=false},
{id=0x346,speaker=0x0201,capture=false},
{id=0x347,speaker=0x0001,capture=true},
{id=0x348,speaker=0x011F,capture=false},
{id=0x349,speaker=0x0125,capture=false},
{id=0x34A,speaker=0x01D3,capture=false},
{id=0x34B,speaker=0x0201,capture=false},
{id=0x06E,speaker=0x0001,capture=false},
{id=0x07B,speaker=0x011F,capture=false},
{id=0x089,speaker=0x0125,capture=false},
{id=0x09D,speaker=0x01D3,capture=false},
{id=0x13D,speaker=0x0201,capture=false},
{id=0x148,speaker=0x0001,capture=false},
{id=0x161,speaker=0x011F,capture=false},
{id=0x186,speaker=0x0125,capture=false},
{id=0x187,speaker=0x01D3,capture=false},
{id=0x189,speaker=0x0201,capture=false},
{id=0x18A,speaker=0x0001,capture=false},
{id=0x19C,speaker=0x011F,capture=false},
{id=0x1C2,speaker=0x0125,capture=false},
{id=0x1C5,speaker=0x01D3,capture=false},
{id=0x1D1,speaker=0x0201,capture=false},
{id=0x1E1,speaker=0x0001,capture=false},
{id=0x1E2,speaker=0x011F,capture=false},
{id=0x1F6,speaker=0x0125,capture=false},
{id=0x218,speaker=0x01D3,capture=false},
{id=0x219,speaker=0x0201,capture=false},
{id=0x21A,speaker=0x0001,capture=false},
{id=0x26F,speaker=0x011F,capture=false},
{id=0x270,speaker=0x0125,capture=false},
{id=0x271,speaker=0x01D3,capture=false},
{id=0x272,speaker=0x0201,capture=false},
{id=0x273,speaker=0x0001,capture=false},
{id=0x274,speaker=0x011F,capture=true},
{id=0x275,speaker=0x0125,capture=true},
{id=0x276,speaker=0x01D3,capture=false},
{id=0x27C,speaker=0x0201,capture=false},
{id=0x283,speaker=0x0001,capture=false},
{id=0x287,speaker=0x011F,capture=false},
{id=0x31D,speaker=0x011F,capture=true},
{id=0x31E,speaker=0x011F,capture=false},
{id=0x336,speaker=0x011F,capture=false},
{id=0x337,speaker=0x011F,capture=false},
{id=0x31B,speaker=0x011F,capture=false},
{id=0x31D,speaker=0x0125,capture=true},
{id=0x31E,speaker=0x0125,capture=false},
{id=0x336,speaker=0x0125,capture=false},
{id=0x337,speaker=0x0125,capture=false},
{id=0x31B,speaker=0x0125,capture=false},
{id=0x31D,speaker=0x01D3,capture=true},
{id=0x31E,speaker=0x01D3,capture=false},
{id=0x336,speaker=0x01D3,capture=false},
{id=0x337,speaker=0x01D3,capture=false},
{id=0x31B,speaker=0x01D3,capture=false},
{id=0x31D,speaker=0x0201,capture=true},
{id=0x31E,speaker=0x0201,capture=false},
{id=0x336,speaker=0x0201,capture=false},
{id=0x337,speaker=0x0201,capture=false},
{id=0x31B,speaker=0x0201,capture=false},
}
assert(maxf==#cases*600)
local n=0;local idx=0;local age=0;local pending=true;local ready=false;local save=false
local entry=false;local draws=0;local prefixes=0;local done=false;local results={};local failed=0
local function capture(label)
 local g=assert(io.open(out..'/'..tag..'-'..label..'.png','wb'));g:write(emu.takeScreenshot());g:close()
end
local function record()
 assert(idx>0)
 local ok=entry and draws>0 and done
 if not ok then failed=failed+1 end
 results[#results+1]=string.format('{"id":"%03X","speaker":%d,"entry":%s,"draws":%d,"prefix_draws":%d,"completed":%s,"status":"%s"}',cases[idx].id,cases[idx].speaker,tostring(entry),draws,prefixes,tostring(done),ok and 'pass' or 'fail')
 p(string.format('CASE_DONE index=%d id=%03X speaker=%04X entry=%s draws=%d prefix=%d completed=%s status=%s',idx,cases[idx].id,cases[idx].speaker,tostring(entry),draws,prefixes,tostring(done),ok and 'pass' or 'fail'))
end
emu.addMemoryCallback(function()
 if save then
  save=false;record();capture('final')
  local g=assert(io.open(out..'/'..tag..'.state','wb'));g:write(emu.createSavestate());g:close()
  g=assert(io.open(out..'/message-runtime-results.json','w'));g:write('{"status":"'..(failed==0 and 'pass' or 'fail')..'","cases":['..table.concat(results,',')..']}');g:close()
  p('SAVED frames='..n);log:close();emu.stop(failed==0 and 0 or 1);return
 end
 if pending then
  pending=false
  if idx>0 then record() end
  idx=idx+1;age=0;entry=false;draws=0;prefixes=0;done=false
  assert(emu.loadSavestate(checkpoint),'checkpoint restore failed')
  local c=assert(cases[idx]);w(0x34A,c.id);w(0x34B,c.id>>8);w(0x34C,c.speaker);w(0x34D,c.speaker>>8)
  if c.id==0x1F6 then w(0x35D,0x3E);w(0x35E,0x44) end
   if c.d and c.d~=0 then w(0x35D,c.d) end
   if c.e and c.e~=0 then w(0x35E,c.e) end
  ready=true;p(string.format('CONTROLLED_MESSAGE index=%d id=%03X speaker=%04X',idx,c.id,c.speaker));return
 end
end,emu.callbackType.exec,0x8000,0xFFFF,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 if ready and word(0x34A)==cases[idx].id then
  assert(word(0x34C)==cases[idx].speaker,'speaker changed before original entry');entry=true
 end
end,emu.callbackType.exec,0x1EB08,0x1EB42,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addMemoryCallback(function()
 if ready and word(0x34A)==cases[idx].id then
  draws=draws+1;local code=r(0x3EA+r(0x3E9));if code>=0xC0 and code<=0xD2 then prefixes=prefixes+1 end
 end
end,emu.callbackType.exec,0x1FA30,0x1FA30,emu.cpuType.snes,emu.memType.snesPrgRom)
emu.addEventCallback(function()
 local press=ready and not done and age>90 and age%16<6
 emu.setInput({a=press,b=press,x=false,y=false,up=false,down=false,left=false,right=false,start=false,select=false,l=false,r=false},0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 if not ready then return end
 n=n+1;age=age+1
 if age==90 and cases[idx].capture then capture(string.format('%03X-%04X',cases[idx].id,cases[idx].speaker)) end
 if entry and draws>0 and age>5 and (r(0x373)==0 or word(0x34A)~=cases[idx].id) then done=true end
 if n>=maxf then save=true elseif age>=600 then pending=true end
end,emu.eventType.endFrame)

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
