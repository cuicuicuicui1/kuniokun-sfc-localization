"""Apply the manifest-pinned BPS; reject overwrites and wrong input."""
from pathlib import Path
import argparse,json,hashlib,os,tempfile
from bps_codec import decode

def apply(source,patch,output,manifest):
 source,patch,output,manifest=map(lambda p:Path(p).resolve(),(source,patch,output,manifest))
 if output.exists() or output in (source,patch,manifest):raise ValueError('输出已存在或与输入同名；请选择新文件，原件不会覆盖')
 m=json.loads(manifest.read_text(encoding='utf8'));raw=source.read_bytes();bps=patch.read_bytes()
 if len(raw)!=m['source']['size'] or hashlib.sha256(raw).hexdigest()!=m['source']['sha256']:raise ValueError(f"输入不匹配：需要清单指定的源 ROM（CRC32 {m['source'].get('crc32','unknown')}）")
 if hashlib.sha256(bps).hexdigest()!=m['patch']['sha256']:raise ValueError('补丁指纹不匹配')
 result=decode(bps,raw)
 if len(result)!=m['target']['size'] or hashlib.sha256(result).hexdigest()!=m['target']['sha256']:raise ValueError('输出验证失败')
 output.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix='.native-cn-',suffix='.tmp',dir=output.parent)
 try:
  with os.fdopen(fd,'wb') as g:g.write(result)
  if output.exists():raise ValueError('输出路径已被其他操作创建；停止覆盖')
  os.rename(tmp,output)
 finally:
  if Path(tmp).exists():Path(tmp).unlink()
 return output
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--patch',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--manifest',type=Path,default=Path(__file__).with_name('release-manifest.json'));a=p.parse_args()
 try:print(apply(a.source,a.patch,a.output,a.manifest))
 except (ValueError, OSError) as e:p.exit(1,str(e)+'\n')
