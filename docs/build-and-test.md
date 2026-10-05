# 构建与测试

[返回首页](../README.md) · [源码导航](code-map.md) · [当前指纹](../notes/current-state.md)

> **先用独立工作副本。** 当前脚本不是无副作用的构建命令：`make_base.py` 会写基线，`cnbuild5.py` 会改写 ROM、IPS 和生成侧车。仅设置 `OUT_ROM` 并不会隔离 IPS 或侧车输出。

## 1. 本地依赖

在仓库根目录运行。维护机已验证的参考环境是 **Python 3.12.14 / Pillow 12.3.0 / Windows 中文字体**；其他环境不自动获得相同字节或兼容性保证。

```powershell
python --version
python -m pip install "Pillow==12.3.0"
```

需要自行准备的资源：

| 路径 | 用途 / 核对方式 |
| --- | --- |
| `dl/roms/kuniokun__SF8127.smc` | 正确日版原 ROM；大小、CRC、SHA 见当前状态 |
| `fonts/unifont.hex.gz` | 16×16 位图字体输入；不随 Git 分发 |
| `C:/Windows/Fonts/msyh.ttc` | 当前 `cnfont8.py` 调用路径的字体输入 |
| `C:/Windows/Fonts/simsun.ttc` | `cnglyph.py` 的部分字体路径与兜底输入 |
| `work_kuniokun_2mb.smc` | 由 `make_base.py` 从正确原版生成 |

`cnglyph.py` 还有字体兜底路径。不同字体文件、Pillow、构建开关均可能改变字形或布局；替换字体后产生的是新候选，不能仅按相似截图宣称复现旧版。

维护机参考资源 SHA-256（rc8 沿用同一输入）（指纹不包含字体文件，也不授予其分发许可）：

```text
fonts/unifont.hex.gz       e66385c79a0b8b24a466f3129930e08a966a935b4bf3b28c6bb17a9df9bf791d
Windows/Fonts/msyh.ttc    d79c55e68b1131eea0cc1c47be4f572d964f28c682e143db2ad09c1e4cb07a3f
Windows/Fonts/simsun.ttc  1526ac24375f51f6eb73bc2d3f8072dbe4a80a3a65217677c9d9a84f67dab2ab
```

仅克隆仓库不能直接完整构建：原 ROM、字库、模拟器和回放用 SRAM 是有意不入库的本地依赖。

## 2. 构建顺序

在新的独立副本中放好上述资源，并确认没有沿用实验参数。新 PowerShell 会话仍可能继承环境变量，必要时显式清除：

```powershell
$overrides = "FIXED_N","HUDFIX","ITEMSG","PACE","HUD_ORIG","PROTECT_GROUPS",`
    "CMDWIN","PROMPT_CLOBBERED","SLOTS_FORCE","LITFIX","BAND_DEBUG","STALEROW",`
    "CHARSTAT","KEEP1_OLD","ENC_TOTAL","BASE_ONLY","OUT_ROM","LITERALFIX",`
    "IDLEPASS","STATUS_LABELS","GLYPH_STRAY","PYTHONOPTIMIZE"
foreach ($name in $overrides) {
    Remove-Item "Env:$name" -ErrorAction SilentlyContinue
}
$env:PYTHONUTF8 = "1"
$env:PYTHONHASHSEED = "0"

python make_base.py
# 前一步非零退出时停止；不要继续构建错误输入。
python cnbuild5.py
# 前一步非零退出时停止；不要用残留文件继续验收。
python verify_all.py
```

PowerShell 的普通多行命令不会自动因 Python 非零退出而停止：每一步都要确认成功。**不要以 `python -O` 或 `PYTHONOPTIMIZE` 禁用断言**；本工程大量保护和校验使用 `assert`。

首次运行 `make_base.py` 后，基线应为 2,097,152 字节、CRC32 `DE95E688`。它等于原版 + 1 MiB 零填充 + 大小/校验和头部更新，不是另一个汉化输入。

## 3. 输出要成套核对

| 文件 | 角色 |
| --- | --- |
| `kuniokun_cn.smc` | 本地运行目标；禁止上传 |
| `kuniokun_cn.ips` | 相对于原版的交付补丁 |
| `cn_build_params.json` | 本次构建的实际参数与布局 |
| `cn_addr_map.json` | 本次文本地址映射 |
| `cn_glyph_cell.json` | 本次字形页/槽映射 |

上述文件必须来自同一构建。复现 rc8 时，与 [当前状态](../notes/current-state.md) 的 ROM/IPS 指纹比较；修改了源码、译文或字体后，使用新的候选名称和记录，不伪装成旧冻结产物。

## 4. 自动检查

```powershell
# 当前目录目标，包含分层重建检查
python verify_all.py

# 明确选择某个候选；三份 JSON 侧车须放在该 ROM 同目录
python verify_all.py "候选目录/kuniokun_cn.smc" --ips "候选目录/kuniokun_cn.ips"

# 仅诊断子集，不是完整验收
python verify_all.py --skip-layers
```

总入口通过 `build_context.py` 建临时副本运行检查，不回写被测交付。它仍依赖原版、字体目录等本地资源；单独拷贝候选 ROM/IPS 并不满足全部测试依赖。

- `CHECKS` 的实际列表在 `verify_all.py`，不要用旧文档的“九个测试”作为当前数量。
- `safe16.py` 是 **INFO**，不是功能 PASS。
- 必须读取每项结果。当前实现可能在测试返回 0 但打印 `SKIP` 时仍以成功退出；**退出 0 不能替代“必测项无跳过”的核对**。
- `--skip-layers` 只减少诊断成本，不能宣称完整验证。
- CPU 模型、补丁重放和静态断言不替代真实模拟器场景，更不替代全流程通关。

## 5. 无头模拟器

模拟器与核心自备；输出使用新的独立目录，不指向玩家 ROM 或存档目录。

Mesen 无 SRAM 冷启动检查（路径按本机修改）：

```powershell
python tools/run_mesen_play.py --mesen "F:/emulators/mesen2/Mesen.exe" --tag cold-smoke --frames 900 --shots "60,300,900" --out hw/cold-smoke
```

rc4 分段实际操作路线：

```powershell
python tools/replay_runtime_names.py --mesen "F:/emulators/mesen2/Mesen.exe" --sram "独立测试存档.srm" --out hw/rc4-route

# 显式启用非空菜单诊断夹具；不是自然取得物品的证明
python tools/replay_runtime_names.py --mesen "F:/emulators/mesen2/Mesen.exe" --sram "独立测试存档.srm" --out hw/rc4-menu-fixtures --include-menu-fixtures
```

路线在 `hw/regression_routes/runtime-names-rc4.json`，要求 `required_sram_sha256` 匹配的已知种子。该 SRAM **不分发**；没有它时不要换个存档然后宣称复现成功，可先运行不需要 SRAM 的冷启动检查。

Snes9x libretro 最小冷启动例子（不是独立桌面模拟器的参数）：

```powershell
python tools/run_snes9x_headless.py --core "本地核心/snes9x_libretro.dll" --rom kuniokun_cn.smc --out hw/snes9x-cold --frames 900 --shots "60,300,900"
```

请检查报告、画面、VRAM 与完成标记。帧数只表示执行长度，不能证明走到目标窗口。同 ROM 检查点可用于接力；跨构建旧即时存档只可作诊断，不替代冷启动验收。


### 地下停车场具名诊断与rc7有限验收

rc7已修复可复现的结算/剧情移动竞态，新ROM同身份原HP三人战、台词/原撤锁/4C回归通过，见[rc7记录](../notes/修复记录_GPT_v39-rc7_停车场剧情交接.md)；用户实体机现场和自然全流程仍待复核。前期源码候选身份与NPC消费者见[主线NPC记录](../notes/排查记录_GPT_20261003_主线NPC与菜单回放.md)。已测消费者、排除的夹具和版本身份见[停车场排查记录](../notes/排查记录_GPT_20261002_地下停车场.md)。在仓库根目录运行；所有状态需有匹配CRC32的 `.json` 侧车，输出目录不得已存在：

```powershell
# 默认输入-only：不改内存、不跳剧情，采集用户同ROM现场。
python tools/run_garage_story.py --rom "自备目标ROM.sfc" --state "同ROM现场.state" --out "新的证据目录" --frames 600 --expect capture

# 单人：用普通按键完成警方对话并尝试进门；必须命中原门动作并实际进入4C。
python tools/run_garage_story.py --rom "自备目标ROM.sfc" --state "同ROM警方对话.state" --out "新的进门证据目录" --auto-dialogue --enter --expect advance

# 显式受控准备：原主循环、菜单关闭的同ROM可玩状态。
# 早期剧情捷径 + 最终敌人起始HP=1/玩家HP=200；不是自然流程或180经验验收。
python tools/run_garage_story.py --rom "自备目标ROM.sfc" --state "同ROM可玩.state" --out "新的夹具目录" --prepare --expect advance

# 无ROM安全单测：不证明游戏流程已通过。
python -m unittest discover -s tests -p test_garage_runner.py -v
```

普通双人场景仅给P1按键可能停在另一玩家等待；此入口不替代Riki CPU配置/验证。`capture` 只有采集意义。`advance`失败返回非零并保留manifest和日志；不要把截图、完成帧数或从别的ROM载入成功升级为通过。


探针现在分开报告`combatMembership / npcRole / moveFlags / gateControl`。`NPC_WAIT`表示原剧情移动等待，`NPC_GATE_WAIT`表示原同行角色门就绪等待；短暂出现后完成是正常消费者进展，不单凭一条等待日志判死锁。`--enter`只控制P1普通按键，不替代P2/力CPU/用户实际同行队伍。来源侧车scope保留在manifest中，受控准备后的input-only续跑仍不是自然主线验收。


### 实体机报告与探针边界（2026-10-03补充）

- 本项目停车场用户在实体机运行最后交付rc6，不能导出存档；自行准备各ROM同身份诊断入口，不把索要SRAM/即时存档当作继续条件。
- `run_garage_story.py`显式传Mesen `--timeout`，分别记录核心/外层期限。Mesen先前默认100秒与Python期限无关，非零退出且缺少完成标记不能证明游戏卡死。
- 输入-only探针保存于原`$00:F333`共用帧等待返回；Start菜单会绕过`F203`主循环。原消费者签名检查涵盖此边界及菜单F703加载；不在endFrame创建状态。
- `NATIVE_MENU_ABI_PROOF calls=0 ... result=UNEXERCISED`表示菜单返回未覆盖。具名真实返回核对A/B、P（含N/Z）、会话字节和栈；manifest保留它，但`capture`不是通过，门`advance`也不替代菜单/自然主线/实体机验收。
- 无ROM安全测试运行：`python -m unittest discover -s tests -p test_garage_runner.py -v`，当前17项。实际菜单回放旧失败/新通过及未削弱敌人的失败战斗见[最新排查记录](../notes/排查记录_GPT_20261003_主线NPC与菜单回放.md)。


### rc7同步钩子与实际证据边界

在独立构建副本运行`python test_garage_sync.py`（32个原消费者/ABI模型例及安装负例），或完整`python verify_all.py`（rc7 当时为23 PASS+1 INFO；当前 rc8 为26 PASS+1 INFO）。`garage_story_patch.py`只增加最终战结算等待，不通过删除NPC/直接改门锁兜底。保留页1F5C00..1F5D00必须完整未占用，hook必须匹配原5字节；错源/重复叠加应失败。

原HP敌人140/170/125与剧情NPC的本轮证据在维护者私有目录，前置是受控event12交接、主角按原成长曲线一次性profile（包含0116/0118有效攻防），后续纯普通按键；独立1800帧门续跑进入4C。这个上游scope不能通过`advance=PASS`改成自然主线。旧35BF候选到新4BDE的同状态对照明确为跨ROM因果诊断，不能拿来替代同身份门验收。菜单返回0调用仍UNEXERCISED；新具名非空气力菜单实际1次PASS。实体机无需提供存档，用新ROM从战前正常进度复核。

## rc8源码注意事项

2026-10-05 根目录 IPS 与三份侧车已同步 rc8；维护机旧根目录 ROM 仍为 rc4，不用于默认验收。新源码必须在独立副本构建，或显式选择与 IPS/侧车匹配的 rc8 目标。rc8最终配置987字形、33槽、30页，采用`glyph_coloring.py`；三份生成侧车来自同批构建。不要手改slot/cell或删掉失败窗口绕过容量错误。

片尾有独立的固定节拍/20真实共显集合/F6五格缩进处理；列车phase80原型已被日版反例否决。只有在eventAC/map27/FEB8清phase0才是最终实现。原正文PACE6与所有普通列车行为保留。

自动检查当前为26 PASS+1 INFO；17项无ROM安全测试另运行`python -m unittest discover -s tests -v`。片尾、停车场和梅田最终消费者检查属于受控入口，不升级成全通关。`hw/mesen_*_jump.lua`需同ROM、菜单关闭、开场结束的游戏检查点；CPU镜像可变，执行追踪按物理PRG地址。跳剧情后停止写内存再续跑。

全文1013项审校表见`notes/text-review-v39-rc8.json`；动态姓名/地名/共享后缀组合没有全部穷举。具体证据、失败排除项和产物指纹见rc8具名记录。
