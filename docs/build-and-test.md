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

rc4 维护机参考资源 SHA-256（指纹不包含字体文件，也不授予其分发许可）：

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

上述文件必须来自同一构建。复现 rc4 时，与 [当前状态](../notes/current-state.md) 的 ROM/IPS 指纹比较；修改了源码、译文或字体后，使用新的候选名称和记录，不伪装成旧冻结产物。

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
