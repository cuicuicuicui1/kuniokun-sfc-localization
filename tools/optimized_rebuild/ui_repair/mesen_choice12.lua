-- Controlled message ID at a same-ROM, cold-generated original call site.
-- The stale VRAM pattern is a negative case; never write success flags.
local out=assert(os.getenv('PLAY_OUT'));local tag=assert(os.getenv('PLAY_TAG'))
local maxf=tonumber(os.getenv('PLAY_FRAMES'));local mem=emu.memType.snesMemory
local prg=emu.memType.snesPrgRom;local vram=emu.memType.snesVideoRam
local f=assert(io.open(os.getenv('PLAY_STATE'),'rb'));local checkpoint=f:read('*a');f:close()
local log=assert(io.open(out..'/'..tag..'.log','w'))
local function p(s)log:write(s..'\n');log:flush()end
local function r(a)return emu.read(a,mem)&255 end
local function w(a,v)emu.write(a,v,mem)end
local function shot(label)local g=assert(io.open(out..'/'..tag..'-'..label..'.png','wb'));g:write(emu.takeScreenshot());g:close()end
local ready=false;local wantSave=false;local n=0;local entry=false;local poisoned=false;local verified=false
local rows=0;local uploads=0;local firstSelection=nil;local sawRight=false;local sawLeft=false;local closed=false
emu.addMemoryCallback(function()
 if not ready then
  assert(emu.loadSavestate(checkpoint));ready=true
  w(0x34A,0x36);w(0x34B,2);w(0x34C,0);w(0x34D,2)
  p('CONTROLLED_MESSAGE 236 speaker0200; original entry, no PC/ROM/story writes');return
 end
 if wantSave then
  assert(entry and poisoned and verified and rows>=3 and sawRight and sawLeft and closed,'incomplete choice interaction')
  local g=assert(io.open(out..'/'..tag..'.state','wb'));g:write(emu.createSavestate());g:close()
  p('CHOICE_PASS native entry; three rows; stale glyph repair; left/right; confirm; exit')
  p('SAVED frames='..n);log:close();emu.stop(0)
 end
end,emu.callbackType.exec,0x8000,0xFFFF,emu.cpuType.snes,mem)
emu.addMemoryCallback(function()if ready then entry=true end end,emu.callbackType.exec,0x1EB08,0x1EB42,emu.cpuType.snes,prg)
emu.addMemoryCallback(function()
 if not poisoned then
  poisoned=true
  for _,s in ipairs({{0x44,3},{0x4A,2},{0x4D,3}}) do
   for i=0,s[2]*16-1 do emu.write(0xC000+s[1]*16+i,0xA5,vram) end
  end
  p('STALE_GLYPH_NEGATIVE_CASE seeded before native draw')
 end
end,emu.callbackType.exec,0x1F141,0x1F141,emu.cpuType.snes,prg)
emu.addMemoryCallback(function()if ready then rows=rows+1 end end,emu.callbackType.exec,0x1F3D2,0x1F3D2,emu.cpuType.snes,prg)
emu.addEventCallback(function()
 local key={a=false,b=false,x=false,y=false,up=false,down=false,left=false,right=false,start=false,select=false,l=false,r=false}
 if ready then
  key.right=(n>=90 and n<98) or (n>=150 and n<158)
  key.left=n>=120 and n<128
  key.y=n>=190 and n<198
  if n>=250 then key.b=n%24<6 end
 end
 emu.setInput(key,0)
end,emu.eventType.inputPolled)
emu.addEventCallback(function()
 if not ready then return end
 n=n+1
 if poisoned and not verified and r(0x392)==3 and r(0x3B7)==0x50 then
  for _,s in ipairs({{0x44,3},{0x4A,2},{0x4D,3}}) do
   for i=0,s[2]*16-1 do assert((emu.read(0xC000+s[1]*16+i,vram)&255)==(emu.read(0xF8000+s[1]*16+i,prg)&255),'font refresh missing') end
  end
  firstSelection=r(0x368);verified=true;shot('options');p('CHOICE_PIXELS_VERIFIED original bitmaps restored')
 end
 if verified and r(0x373)==0xC0 then
  if n>=100 and n<120 and r(0x368)==1 then sawRight=true end
  if n>=130 and n<150 and r(0x368)==0 then sawLeft=true end
 end
 if verified and n>200 and r(0x373)~=0xC0 then closed=true end
 if n==180 then shot('right') end
 if n==500 then shot('after') end
 if n%60==0 then p(string.format('FRAME %d stage=%d msg=%02X choice=%d rows=%d',n,r(0x392),r(0x373),r(0x368),rows)) end
 if n>=maxf then wantSave=true end
end,emu.eventType.endFrame)
