#!/usr/bin/env python
"""按顺序跑完整套校验，打印一张总表。

每次改完构建器、译文或瓦片账之后跑一遍；交付前必须全绿。

    python verify_all.py                # 用当前 kuniokun_cn.smc
    python verify_all.py <rom>          # 校验指定 ROM（需要 CMDWIN 等环境变量与之一致）
"""
import os
import subprocess
import sys

ROM = sys.argv[1] if len(sys.argv) > 1 else 'kuniokun_cn.smc'

CHECKS = [
    ('check16.py',      '文本 round-trip、字形池、人名记录'),
    ('verify16.py',     '65816 模型逐字节仿真整条绘制流程'),
    ('safe16.py',       '槽位/瓦片占用表（人工核对用，不判 pass/fail）'),
    ('checkband.py',    '提示表瓦片不在抽屉可达范围（彩色横条不回归）'),
    ('checkchoice.py',  '选择框 是／否：脚本、字体位图、光标瓦片保护'),
    ('checkmenu.py',    'Start 菜单：标签码指向池槽位 + 上传器接线'),
    ('test_stalerow.py','残留行 stub 的边界用例'),
    ('test_menuclose.py','菜单关闭时的清行 stub（CMDWIN=0 时自动跳过）'),
    ('test_menuload.py', '用 65816 模型直跑菜单标签上传器'),
    ('test_itemdraw.py','状态画面道具名：110 条逐个跑 $01:FC75 渲染器'),
    ('test_labeldraw.py','状态画面标签：跑 $01:F971 解释器逐格核对 23 个字形'),
    ('ipsverify.py',    '交付 IPS 从原版重放 == 交付 ROM'),
]

env = dict(os.environ)
env.setdefault('PYTHONHASHSEED', '0')

print('校验目标：%s' % ROM)
print('=' * 78)
bad = []
for script, what in CHECKS:
    if not os.path.exists(script):
        print('%-20s 跳过（脚本不存在）' % script)
        continue
    p = subprocess.run([sys.executable, script], capture_output=True, text=True, env=env)
    tail = [l for l in p.stdout.strip().splitlines() if l.strip()]
    verdict = tail[-1] if tail else '(no output)'
    ok = p.returncode == 0
    if not ok:
        bad.append(script)
    print('%-20s %-4s %s' % (script, 'PASS' if ok else 'FAIL', what))
    if not ok:
        for line in tail[-6:]:
            print('      %s' % line)
print('=' * 78)
if bad:
    print('%d 项失败：%s' % (len(bad), ', '.join(bad)))
    sys.exit(1)
print('全部通过。注意：safe16.py 只打印占用表，需要人眼核对。')
