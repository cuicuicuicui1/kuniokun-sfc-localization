"""Verify the selected ROM and matching sidecars in an isolated checkout.

python verify_all.py [ROM] [--ips IPS] [--skip-layers]
ROM metadata is read from the selected ROM's directory. Missing tests FAIL.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zlib
from build_context import stage_project, ROOT

CHECKS = [
    ('check16.py',      '文本 round-trip、字形池、人名记录'),
    ('verify16.py',     '65816 模型逐字节仿真整条绘制流程'),
    ('safe16.py',       '槽位/瓦片占用表（人工核对用，不判 pass/fail）'),
    ('checkband.py',    '提示表瓦片不在抽屉可达范围（彩色横条不回归）'),
    ('checkchoice.py',  '选择框 是／否：脚本、字体位图、光标瓦片保护'),
    ('checkmenu.py',    'Start 菜单：标签码指向池槽位 + 上传器接线'),
    ('test_stalerow.py','真实 tick：换行补空不能擦掉刚写完的对白'),
    ('test_menuclose.py','菜单关闭时的清行 stub（CMDWIN=0 时自动跳过）'),
    ('test_menuload.py', '用 65816 模型直跑菜单标签上传器'),
    ('test_itemdraw.py','状态画面道具名：110 条逐个跑 $01:FC75 渲染器'),
    ('test_labeldraw.py','状态画面标签：跑 $01:F971 解释器逐格核对 23 个字形'),
    ('test_hudname.py','战斗 HUD：完整 $00:8C34 调用链、560 条名字、队列边界'),
    ('test_itemmsg.py','消息里的道具名：跑抽屉 $DE 分支核对取 id/上传/写格/推列'),
    ('test_hud_tiles.py', 'HP 图形与中文字形隔离，原版敌我血条共享像素/保留调色板'),
    ('test_pace_hdma.py', '打字倒计时与 BG3 HDMA 底边滚动表隔离（旧版负例）'),
    ('test_pace.py',   '消息节拍：按住 A/B、松开恢复、边沿隔离、补空与队列'),
    ('check_layers.py', '开关组合覆盖：BASE_ONLY/off/on 三档构建+检查'),
    ('test_verification.py', '校验器负例：损坏 IPS、错误 ROM、DEC 标志'),
    ('ipsverify.py',    '交付 IPS 从原版重放 == 交付 ROM'),
]

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom',nargs='?',type=Path,default=ROOT/'kuniokun_cn.smc')
    parser.add_argument('--ips',type=Path)
    parser.add_argument('--skip-layers',action='store_true',help='diagnostic subset only, not release acceptance')
    args=parser.parse_args(argv)
    rom=args.rom.resolve();ips=(args.ips or rom.with_suffix('.ips')).resolve()
    required=[ROOT/name for name,_ in CHECKS]+[rom,ips]
    required += [rom.parent/name for name in ('cn_build_params.json','cn_addr_map.json','cn_glyph_cell.json')]
    missing=[str(p) for p in required if not p.is_file()]
    if missing:
        print('FAIL: missing required inputs/tests:',*missing,sep='\n');return 1
    env=dict(os.environ,PYTHONHASHSEED='0',PYTHONUTF8='1')
    print(f'Target: {rom} CRC32={zlib.crc32(rom.read_bytes()):08X}',flush=True)
    bad=[]
    with tempfile.TemporaryDirectory(prefix='sfc-verify-') as tmp:
        work=stage_project(tmp,rom=rom,ips=ips)
        import shutil
        for name in ('cn_build_params.json','cn_addr_map.json','cn_glyph_cell.json'):
            shutil.copy2(rom.parent/name,work/name)
        for name,what in CHECKS:
            if name=='check_layers.py' and args.skip_layers:
                print('SKIP: layer builds (explicit diagnostic mode)',flush=True);continue
            cmd=[sys.executable,str(work/name)]
            if name=='test_menuload.py':cmd.append(str(work/'kuniokun_cn.smc'))
            proc=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
            skipped='SKIP:' in proc.stdout
            ok=proc.returncode==0
            print(f'{name:24s} {"FAIL" if not ok else "SKIP" if skipped else "INFO" if name=="safe16.py" else "PASS"} {what}',flush=True)
            if not ok:
                bad.append(name)
                print((proc.stdout+'\n'+proc.stderr)[-6000:],flush=True)
    print(f'{len(bad)} failed. '+('Diagnostic subset only.' if args.skip_layers else 'Full verification finished.'))
    print('Model/static checks are not a substitute for emulator/playthrough acceptance.')
    return bool(bad)

if __name__=='__main__':raise SystemExit(main())
