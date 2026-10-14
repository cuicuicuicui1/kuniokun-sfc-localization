"""Resolve local source/emulator dependencies without maintenance-machine paths."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent
def source_tree():
 explicit=os.environ.get('SFC_RECON_SOURCE')
 candidates=[Path(explicit)] if explicit else [ROOT/'汉化基座源码',ROOT.parent.parent,Path.home()/'.zcode/workspace/default/sfc-recon']
 for p in candidates:
  if (p/'cnbuild5.py').is_file():return p.resolve()
 raise FileNotFoundError('Set SFC_RECON_SOURCE to the Chinese source tree containing cnbuild5.py')
def mesen_paths():
 src=source_tree();runner=Path(os.environ.get('SFC_MESEN_RUNNER',str(src/'tools/run_mesen_play.py')))
 configured=os.environ.get('SFC_MESEN_EXE')
 if configured:exe=Path(configured)
 else:exe=ROOT.parents[1]/'work/garage-event-20261002/emulator/KunioGarageMesen.exe'
 if not runner.is_file():raise FileNotFoundError('Set SFC_MESEN_RUNNER to run_mesen_play.py')
 if not exe.is_file():raise FileNotFoundError('Set SFC_MESEN_EXE to your private Mesen executable')
 return runner.resolve(),exe.resolve()
