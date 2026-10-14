from pathlib import Path
import json,sys,subprocess,os,hashlib
from runtime_paths import source_tree
ROOT=Path(__file__).resolve().parent;SRC=source_tree()
# Current candidate, never import a test's old root ROM by accident.
tasks=[(ROOT/'verify_port.py',[]),(ROOT/'verify_ui.py',[]),(ROOT/'audit_source.py',[]),(ROOT/'audit_native_hooks.py',[]),(ROOT/'test_payload_integrity.py',[]),(ROOT/'test_parameter_regression.py',[]),(ROOT/'test_font_lifetime.py',[]),(ROOT/'audit_macro_windows.py',[]),(ROOT/'audit_buffer.py',[]),(ROOT/'test_optimized_combat.py',[]),(ROOT/'test_input_modifiers.py',[]),(ROOT/'test_extended_hud_lifetime.py',[]),(ROOT/'test_hudname_ui.py',[str(ROOT/'candidate-ui.sfc')]),(SRC/'test_runtime_names.py',[str(ROOT/'candidate-ui.sfc')])]
tasks.append((ROOT/'test_crowded_consumers.py',[]))
results=[]
for script,args in tasks:
 proc=subprocess.run([sys.executable,str(script),*args],cwd=SRC,env=dict(os.environ,PYTHONUTF8='1'),capture_output=True,text=True,encoding='utf-8')
 log=ROOT/'code-check-logs';log.mkdir(exist_ok=True);(log/(script.stem+'.log')).write_text(proc.stdout+proc.stderr,encoding='utf-8')
 print(script.name,'PASS' if proc.returncode==0 else 'FAIL',flush=True)
 if proc.returncode!=0:print(proc.stdout+proc.stderr);raise SystemExit(proc.returncode or 1)
 results.append({'test':script.name,'exit':proc.returncode,'log_sha256':hashlib.sha256((proc.stdout+proc.stderr).encode()).hexdigest()})
report={'status':'pass','candidate_sha256':hashlib.sha256((ROOT/'candidate-ui.sfc').read_bytes()).hexdigest(),'tests':results,'scope':'static/source parity and native CPU/queue models; Mesen/Snes9x results are separate'}
(ROOT/'code-checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
