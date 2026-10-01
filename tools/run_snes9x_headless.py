"""Minimal headless libretro regression runner; reads ROM, never writes player SRAM.
ABI definitions follow the official libretro.h (saved in sources/).
"""
import argparse, ctypes as C, hashlib, json, os, re, zlib
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--core',required=True);p.add_argument('--rom',required=True);p.add_argument('--out',required=True);p.add_argument('--frames',type=int,default=900);p.add_argument('--shots',default='60,180,360,600,900');p.add_argument('--input',default='');p.add_argument('--route');p.add_argument('--sram');p.add_argument('--state');p.add_argument('--fixture',choices=('menu-names',));a=p.parse_args()
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
rom=Path(a.rom).resolve();raw=rom.read_bytes();before=hashlib.sha256(raw).hexdigest()
core=C.CDLL(str(Path(a.core).resolve()))
class Info(C.Structure): _fields_=[('name',C.c_char_p),('version',C.c_char_p),('extensions',C.c_char_p),('need_fullpath',C.c_bool),('block_extract',C.c_bool)]
class Game(C.Structure): _fields_=[('path',C.c_char_p),('data',C.c_void_p),('size',C.c_size_t),('meta',C.c_char_p)]
class Variable(C.Structure): _fields_=[('key',C.c_char_p),('value',C.c_char_p)]
ENV=C.CFUNCTYPE(C.c_bool,C.c_uint,C.c_void_p); VIDEO=C.CFUNCTYPE(None,C.c_void_p,C.c_uint,C.c_uint,C.c_size_t); AUDIO=C.CFUNCTYPE(None,C.c_int16,C.c_int16); BATCH=C.CFUNCTYPE(C.c_size_t,C.c_void_p,C.c_size_t); POLL=C.CFUNCTYPE(None); INPUT=C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
variables={};pixel_format=0;env_calls={};frame=0;video_calls=0;last=None;records=[]
rootbytes=str(out).encode();sysinfo=Info();core.retro_get_system_info(C.byref(sysinfo))
print(sysinfo.name,sysinfo.version,sysinfo.need_fullpath,flush=True)
@ENV
def environment(cmd,data):
 global pixel_format
 env_calls[cmd]=env_calls.get(cmd,0)+1
 if cmd==3: C.cast(data,C.POINTER(C.c_bool))[0]=True;return True
 if cmd in (9,30,31): C.cast(data,C.POINTER(C.c_char_p))[0]=rootbytes;return True
 if cmd==10: pixel_format=C.cast(data,C.POINTER(C.c_int))[0];return pixel_format in (0,1,2)
 if cmd in (11,18,35): return True
 if cmd==15:
  v=C.cast(data,C.POINTER(Variable)).contents;v.value=variables.get(v.key);return v.value is not None
 if cmd==16:
  table=C.cast(data,C.POINTER(Variable));i=0
  while table[i].key:
   variables[table[i].key]=table[i].value.split(b'; ',1)[-1].split(b'|')[0];i+=1
  return True
 if cmd==17: C.cast(data,C.POINTER(C.c_bool))[0]=False;return True
 if cmd==52: C.cast(data,C.POINTER(C.c_uint))[0]=0;return True
 return False
@VIDEO
def video(data,w,h,pitch):
 global last,video_calls
 video_calls+=1
 if data: last=(C.string_at(data,pitch*h),w,h,pitch,pixel_format)
@AUDIO
def audio(l,r): pass
@BATCH
def batch(data,n): return n
@POLL
def poll(): pass
ids={'b':0,'y':1,'select':2,'start':3,'up':4,'down':5,'left':6,'right':7,'a':8,'x':9,'l':10,'r':11}
if a.route:
 route=json.loads(Path(a.route).read_text(encoding='utf-8'));a.input=route['input'];a.frames=route['frames'];a.shots=','.join(map(str,route['shots']))
events=[(int(lo),int(hi),[ids[x] for x in re.split('[,+]',keys)]) for lo,hi,keys in re.findall(r'(\d+)-(\d+):([\w,+]+)',a.input)]
@INPUT
def input_state(port,device,index,button):
 return int(port==0 and device==1 and any(lo<=frame<hi and button in keys for lo,hi,keys in events))
for name,ctype,cb in [('environment',ENV,environment),('video_refresh',VIDEO,video),('audio_sample',AUDIO,audio),('audio_sample_batch',BATCH,batch),('input_poll',POLL,poll),('input_state',INPUT,input_state)]:
 fn=getattr(core,'retro_set_'+name);fn.argtypes=[ctype];fn(cb)
core.retro_load_game.argtypes=[C.POINTER(Game)];core.retro_load_game.restype=C.c_bool
core.retro_get_memory_data.argtypes=[C.c_uint];core.retro_get_memory_data.restype=C.c_void_p
core.retro_get_memory_size.argtypes=[C.c_uint];core.retro_get_memory_size.restype=C.c_size_t
core.retro_serialize_size.restype=C.c_size_t
core.retro_unserialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_unserialize.restype=C.c_bool
core.retro_serialize.argtypes=[C.c_void_p,C.c_size_t];core.retro_serialize.restype=C.c_bool
core.retro_set_controller_port_device.argtypes=[C.c_uint,C.c_uint]
core.retro_init();buf=C.create_string_buffer(raw);game=Game(str(rom).encode('utf-8'),C.cast(buf,C.c_void_p),len(raw),None)
assert core.retro_load_game(C.byref(game)),'load failed'
core.retro_set_controller_port_device(0,1);core.retro_set_controller_port_device(1,1)
if a.state:
 assert not a.sram, 'cannot load state and seed SRAM together'
 statepath=Path(a.state).resolve();meta=json.loads((statepath.parent/'report.json').read_text(encoding='utf-8'))
 assert meta['rom_sha256']==before and meta['name']==sysinfo.name.decode() and meta['version']==sysinfo.version.decode(), 'state is from a different ROM/core'
 statedata=statepath.read_bytes();statebuf=C.create_string_buffer(statedata)
 assert core.retro_unserialize(statebuf,len(statedata)), 'state load failed'
if a.sram:
 seed=Path(a.sram).read_bytes();assert len(seed)<=core.retro_get_memory_size(0);C.memmove(core.retro_get_memory_data(0),seed,len(seed))
if a.fixture:
 assert a.state, 'controlled menu fixture requires an existing same-ROM/core gameplay state'
 assert core.retro_get_memory_size(2)>=0x140, 'system WRAM unavailable'
 ptr=core.retro_get_memory_data(2)
 C.memmove(ptr+0x0102,bytes((99,)),1)
 C.memmove(ptr+0x011E,bytes((8,28,29,30,31,32,33,34,35)),9)
 print('FIXTURE: runtime level=99, inventory IDs 28..35; no PC/scene or SRAM writes',flush=True)
shots={int(f) for f in a.shots.split(',')};shots.add(a.frames)
def save_frame(f):
 if not last: records.append({'frame':f,'video':False});return
 b,w,h,pitch,fmt=last
 if fmt==1: image=Image.frombytes('RGB',(w,h),b,'raw','BGRX',pitch)
 else:
  import numpy as np
  data=np.frombuffer(b,dtype='<u2').reshape(h,pitch//2)[:,:w].astype('uint32')
  r=(data>>(11 if fmt==2 else 10))&31;g=(data>>5)&(63 if fmt==2 else 31);blue=data&31
  image=Image.fromarray(np.stack([r*255//31,g*255//(63 if fmt==2 else 31),blue*255//31],axis=-1).astype('uint8'))
 image.save(out/f'frame-{f}.png')
 ram=C.string_at(core.retro_get_memory_data(2),core.retro_get_memory_size(2));(out/f'frame-{f}.ram').write_bytes(ram)
 record={'frame':f,'video_calls':video_calls,'width':w,'height':h,'pixel_format':fmt,'pixel_sha256':hashlib.sha256(image.tobytes()).hexdigest(),'colors':len(image.getcolors(w*h) or []),'ram_sha256':hashlib.sha256(ram).hexdigest()}
 records.append(record);print(record,flush=True)
for frame in range(a.frames):
 core.retro_run()
 if frame+1 in shots:save_frame(frame+1)
size=core.retro_serialize_size();state=C.create_string_buffer(size);assert core.retro_serialize(state,size);(out/'end.state').write_bytes(state.raw)
core.retro_unload_game();core.retro_deinit()
assert hashlib.sha256(rom.read_bytes()).hexdigest()==before
report={'core':a.core,'name':sysinfo.name.decode(),'version':sysinfo.version.decode(),'rom_sha256':before,'rom_crc32':f'{zlib.crc32(raw):08X}','frames':a.frames,'shots':records,'environment_calls':env_calls,'variables':{k.decode():v.decode() for k,v in variables.items()},'input':a.input,'sram_seed':a.sram,'loaded_state':a.state,'runtime_fixture':a.fixture,'scope':'bounded execution and screenshots; inspect images to determine game progression'}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
