"""Stage build/test inputs so verification cannot overwrite a live release."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent

def stage_project(destination, source=ROOT, rom=None, ips=None):
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if path.is_file() and (path.suffix in ('.py','.json') or path.name in ('work_kuniokun_2mb.smc','kuniokun_cn.smc','kuniokun_cn.ips')):
            shutil.copy2(path,destination/path.name)
    for relative in ('dl/roms/kuniokun__SF8127.smc',):
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/relative,target)
    (destination/'fonts').mkdir(exist_ok=True)
    for path in (source/'fonts').iterdir():
        if path.is_file() and path.suffix!='.zip':shutil.copy2(path,destination/'fonts'/path.name)
    if rom is not None:shutil.copy2(rom,destination/'kuniokun_cn.smc')
    if ips is not None:shutil.copy2(ips,destination/'kuniokun_cn.ips')
    return destination
