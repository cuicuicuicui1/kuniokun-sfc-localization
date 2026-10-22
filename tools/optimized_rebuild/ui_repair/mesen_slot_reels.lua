-- Native slot renderer regression. The same-ROM checkpoint was made by cold
-- boot. Select message236 and prompt-set1 at its original initialization;
-- this is a controlled consumer test, not a natural arcade encounter.
local out=assert(os.getenv('PLAY_OUT'));local tag=assert(os.getenv('PLAY_TAG'))
local maxf=tonumber(os.getenv('PLAY_FRAMES'));local mem=emu.memType.snesMemory
local prg=emu.memType.snesPrgRom;local vm=emu.memType.snesVideoRam
local state=assert(io.open(os.getenv('PLAY_STATE'),'rb'));local checkpoint=state:read('*a');state:close()
local src=assert(io.open(os.getenv('SLOT_ORIGINAL'),'rb'));local original=src:read('*a');src:close()
assert(#original==0x180000,'wrong original input size')
local log=assert(io.open(out..'/'..tag..'.log','w'))
local function p(s)log:write(s..'\n');log:flush()end
local function r(a)return emu.read(a,mem)&255 end
local function shot(label)local f=assert(io.open(out..'/'..tag..'-'..label..'.png','wb'));f:write(emu.takeScreenshot());f:close()end
local n=0;local ready=false;local init=false;local save=false
local frames=0;local bad=0;local stopped=false;local closed=false;local symbols={};local queued=0
local isNegative=os.getenv('EXPECT_OLD_FAILURE')=='1'
emu.addMemoryCallback(function()
 if not ready then
  assert(emu.loadSavestate(checkpoint));ready=true
  emu.write(0x34A,0x36,mem);emu.write(0x34B,2,mem);emu.write(0x34C,0,mem);emu.write(0x34D,2,mem)
  p('CONTROLLED native message236');return
 end
 if save then
  local seen=0;for _,_ in pairs(symbols) do seen=seen+1 end
  local ok=init and stopped and closed and frames>50 and seen==8 and (isNegative and bad>0 or not isNegative and bad==0)
  p(string.format('SLOT_RESULT glyph_frames=%d bad=%d native_symbols=%d stopped=%s closed=%s queues=%d expected_old_failure=%s pass=%s',frames,bad,seen,tostring(stopped),tostring(closed),queued,tostring(isNegative),tostring(ok)))
  assert(ok,'slot consumer regression failed')
  local f=assert(io.open(out..'/'..tag..'.state','wb'));f:write(emu.createSavestate());f:close()
  p('SAVED frames='..n);log:close();emu.stop(0)
 end
end,emu.callbackType.exec,0x8000,0xFFFF,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()
 if ready and not init then init=true;emu.write(0x363,1,mem);p('CONTROLLED prompt-set1 at original F141; no PC/story-success writes') end
end,emu.callbackType.exec,0x1F141,0x1F141,emu.cpuType.snes,prg)
emu.addMemoryCallback(function()queued=queued+1 end,emu.callbackType.exec,0x187000,0x187000,emu.cpuType.snes,prg)
emu.addEventCallback(function()
 local k={a=false,b=false,x=false,y=false,up=false,down=false,left=false,right=false,start=false,select=false,l=false,r=false}
 if ready and r(0x392)==9 then k.y=n%90<4 end
 if ready and n>450 then k.a=n%16<4;k.b=k.a end
 emu.setInput(k,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 if not ready then return end
 n=n+1
 if init and r(0x392)==9 then
  frames=frames+1;local same=true
  for _,spec in ipairs({{0x4A,8},{0x53,1}}) do
   for i=0,spec[2]*16-1 do
    if (emu.read(0xC000+spec[1]*16+i,vm)&255)~=original:byte(0xF8000+spec[1]*16+i+1) then same=false end
   end
  end
  if not same then bad=bad+1 end
  for i=0,2 do local tile=emu.read((0x7BD3+i*2)*2,vm)&255;if tile>=0x4A and tile<=0x51 then symbols[tile]=true end end
  if frames==30 then shot('reels') end
 end
 if init and r(0x396)==3 then stopped=true end
 if stopped and r(0x373)~=0xC0 then closed=true end
 if n>=maxf then save=true end
end,emu.eventType.endFrame)
