# current-state — 初代热血硬派（SFC）汉化

> 2026-09-21 深夜更新。工作目录 `C:\Users\<user>\.zcode\workspace\default\sfc-recon`；
> 交付目录 `F:\BaiduNetdiskDownload\SFC deepseek\初代热血硬派-汉化`。
> 未完成项与红线见同目录 `交接文档.md`。

## 输入与产物

| 项 | 值 |
|---|---|
| 干净原版 | `dl/roms/kuniokun__SF8127.smc`，1 048 576 B，CRC32 `56C05339`，SHA-256 `8F289AC5677508F7…` |
| 构建基线 | `work_kuniokun_2mb.smc` = 原版 + 1 MB 零填充 + 3 个头部字节（`0x7FD7` 大小 `0A→0B`、`0x7FDC/0x7FDE` 校验和/补码）。2 096 592 B，CRC32 `DE95E688` |
| 当前交付构建 | **v22**：ROM CRC32 `8E7D8CC2`，SHA-256 `0EDA9D3C6A2F09DB…`；IPS CRC32 `C242CD0F`；内部校验和 `0x715F` |
| 上一版 | v19：ROM `E798D946` / IPS `3D8B6BDC`——用户实机确认选择框 是／否 正确、状态画面恢复原版 |
| 构建命令 | `PYTHONHASHSEED=0 python cnbuild5.py`（**无环境变量 = v19**；必须固定 hash 种子，否则码页分配不可复现） |

三个构建指针（候选 / 最近静态通过 / 最近运行通过）都指向 v19；普通构建命令即可复现，
连续两次构建 ROM 与 IPS 字节一致（本会话实测）。

## 阶段汇总

- G0 输入与原版基线：**pass**（原版哈希 + 原版场景截图）
- G1 资源链：**pass**（抽屉钩子 `$03:FA30 → $3E:8200`，槽位表、字形池、上传队列均已实测）
- G2 无改文往返：**pass**（`verify16.py` 7078 次绘制仿真、`safe16.py` 布局检查）
- G3 中文最小切片：**pass**（实机截图：`力 :猪肉包一个! / 国夫:力!`）
- G4 稳定构建工具：**pass**（连续两次构建字节一致；`check16/verify16/safe16/checkband/checkchoice` 全绿）
- G5 目标范围扩展：**pass** —— 1013 条文本、560 条人名记录、选择框（v19）、命令窗口（v20）已汉化，
  状态画面保持原版；唯一取舍是菜单标签为单字（见 v20 条目）
- G6 干净重建与发布验收：**partial** —— 原版 → IPS → 逐字节等于已测 ROM（`ipsverify.py identical: True`，
  `47E4F29C`）已通过；双模拟器回归、冷启动通关、实机（真机）验证未做

## v20 相对 v19 的改动

**Start（暂停）菜单汉化**：气／物／装／态／扔（原版 きりょくをつかう 等）。每个菜单项一个汉字——
两字标签会让池子从 36 槽掉到 34 槽、着色窗口从 `main=1 list=9` 崩到 `list=4`，那是**降低安全性**。
五个字里四个用"永远配不成对"的空闲瓦片（字形池的半边必须是连续两张，这些单张它用不了），
第五个用一对；窗口与槽位数与 v19 完全相同。位置不动（引擎的光标指着那几格）。

## v19 相对 v18 的改动

1. **选择框汉化（是／否）**。原版文字行只有 8 像素高（假名单瓦片 `$44/$45/$46`），装不下汉字，
   所以行数不变、两个选项改成 16×16：上行 `$7BC0` 放 (TL,TR)、下行 `$7BE0` 放 (BL,BR)。
   是 = `$44,$45,$46,$4F`，否 = `$4A,$4B,$4D,$4E`，墨色 1 / 底色 2（与原版假名同色）。
   块脚本（`$03:F47B` / `$03:F491`）只改瓦片号，**属性原样保留**（角瓦片的翻转位）。
2. **删掉提示表区域的盲 kana 改写**：那段是脚本数据，不是文字。它把 `$A4` 改成 `$54`，
   并把提示集 1 的块指针 `$F4AD/$F4C1/$F4D5` 改成 `$F45D/$F471/$F455`（真跑进去会写坏 `$040A`）。
   `checkchoice.py` 断言该区域非瓦片字节与原版逐字节相同。
3. **光标箭头瓦片 `$47` 纳入保护**（原先会被池子覆盖，箭头迟早花）。
4. **字体"方框底边缺口"修正**：Unifont 给 日/白/石/苦/否… 这类字把口的底线放在第 14 行、
   第 15 行还留两条竖边，看着像没封口。命中 62 个字形，逐个人眼核对全部变好、无误伤。
   `cnglyph.close_box_bottom()`，`GLYPH_STRAY=0` 可关。
5. **状态画面恢复原版片假名**：`HUD_ORIG` 默认改为 **1**。旧记录说"需要 22 对瓦片"是**过期结论**
   （那时还把死代码道具名表的片假名一起保护着）；实测现在与关闭时同价：保护 68、自由 89 对、
   36 槽、窗口 `main=1 list=9` 完全一致，状态画面绘制脚本与原版**逐字节相同**。
6. 瓦片账：保护 **68**（v18 为 63）、自由 **89** 对（原 93）、着色 **36** 槽（原 38）。
   着色窗口 `main=1 list=9` **没有变小**，安全性不变。

## v15 相对 v14 的改动

**残留行修复**（`STALEROW` 默认 1）。门控从实测数据推出：`$0391` 是要擦的那一行、`$036E` 比它大 1。
队列满时改为**跳过**，不再调用引擎刷写器（v14 整屏乱码的嫌疑根因）。
余量判据从 `2 × ROW_WIPE` 改成 `ROW_WIPE + GLYPH_COST`。

## v14 相对 v13 的改动

1. **中文 Start 菜单**（`CMDWIN=1`，v14 默认开，v15 起因预算不足改回默认关）：5 个标签
   气力/道具/装备/状态/扔掉，10 个静态 8×16 字形放在标签让出的瓦片对上，`$03:F743` 单元表重写。
2. **选项窗乱码修复**：`fix_prompt_tiles()` 迭代求出"池子会占用的提示表瓦片"不动点；
   `checkband.py` 断言提示表瓦片全部在抽屉可达范围之外。
3. **不再保护死掉的文本组**（`PROTECT_GROUPS=stat`）：道具名表（`$01:F7CC` 全 ROM 无引用，死代码）与
   560 条人名记录不再占用字库瓦片。

## v22：菜单两字标签（`CMDWIN=2`，现在是默认）

Start 菜单 = 气力 / 道具 / 装备 / 状态 / 扔掉。标签从字形池里画，**不占常驻瓦片**（36 槽、`list=9` 不变）。
运行时由 `$03:F841` 上的 236 字节 stub 分 4 帧把 10 个字形搬进槽位。新增 `test_menuload.py`
（65816 模型直跑 stub）与 `checkmenu.py`。实机已确认。回退：`CMDWIN=1`（单字）或 `CMDWIN=0`（日文）。

## 已知未解决项

| 问题 | 状态 | 下一步 |
|---|---|---|
| 上一条消息的残留行 | **已修**（v15） | 边界情形未覆盖，回退开关 `STALEROW=0` |
| 选择框（はい／いいえ）乱码 | **已修**（v18） | — |
| 选择框翻译（是／否） | **已做**（v19） | 等用户实机确认 |
| Start 菜单中文 | **已做**（v20，单字标签） | 回退开关 `CMDWIN=0`；两字标签需改走字形池（交接 §4b） |
| 状态画面（HUD）的片假名被改写成平假名 | **已修**（v19，`HUD_ORIG=1`） | 回退开关 `HUD_ORIG=0` |
| 字体 62 个"方框底边缺口"字形 | **已修**（v19） | 回退开关 `GLYPH_STRAY=0` |
| 双模拟器 / 冷启动通关 / 真机 | not_run | 需要 Mesen2 或 snes9x 走一遍流程 |

### 残留行（v15 已修）

门控 `($036E - $0391) & 0x0F == 1` 且列 1..4，擦 `$0391` 整行；余量不足就跳过，绝不调用刷写器。
依据：`hw/seq1.log` 901 帧中 `$0391` 只变过一次（f2711 `04→05`），残留行可见时（f2592）
`$036E=05 / $0391=04`。回退：`STALEROW=0` 构建。

## 工具与命令

| 用途 | 命令 |
|---|---|
| 构建 | `PYTHONHASHSEED=0 python cnbuild5.py` |
| 离线校验 | `python check16.py` / `verify16.py` / `safe16.py` / `checkband.py` / `checkchoice.py` / `test_menuclose.py` |
| stub 仿真 | `python test_stalerow.py` |
| 选择框渲染 | `python prev_choice.py <rom> out.png [set]` |
| IPS 往返 | `python ipsverify.py`（比对交付目录，必须 `identical: True`） |
| 实机 A/B | `HW_TAG=x EmuHawk.exe --lua=hw/band.lua <rom 绝对路径>` → `python bandcheck.py a b` |
| 实机 VRAM dump | `HW_TAG=x HW_NF=3000 HW_EVERY=10 EmuHawk.exe --lua=hw/vramdump.lua <rom>` |
| 强制画选择框 | `HW_TAG=x HW_AT=1400 EmuHawk.exe --lua=hw/forcebox.lua <rom>` |
| 命令窗口预览 | `python prev_rom_cmdwin.py kuniokun_cn.smc out.png` |

**EmuHawk 陷阱**：`client.getpixel` 在本版本**不存在**（读像素只能截图后离线分析）；
`client.screenshot(name)` 不加扩展名，文件落在 `hw/`；ROM 必须绝对路径；启动偶发秒退（重试）；
跑完窗口常驻（下次启动前 taskkill）；内存域只有 `WRAM/VRAM/CARTROM`（没有 CGRAM/OAM）。

## 环境开关（全部记录在 `cn_build_params.json`，校验脚本用 `cb.load_build_params()` 读取）

- `PROTECT_GROUPS`（默认 `stat`）：`item`/`names`/`stat` 三组谁还占字库瓦片
- `PROMPT_CLOBBERED`（默认 `209`，构建时会迭代成不动点）
- `CMDWIN`（默认 `1`）、`STALEROW`（默认 `1`；`=0` 回退、`=count` 只装计数器）、
  `HUD_ORIG`（默认 `1`）、`SLOTS_FORCE`（仅测量用）、`GLYPH_STRAY`（默认 `1`）
