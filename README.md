# 初代热血硬派（SFC）简体中文汉化 — 工具链与记录

《初代熱血硬派くにおくん》（Technōs Japan, 1992, SF8127）的汉化工程：逆向记录、构建器、
翻译数据、校验脚本、模拟器探针与交付文档。

**先读 [`交接文档.md`](交接文档.md)**（当前状态、红线、未完成项、坑），
阶段状态见 [`notes/current-state.md`](notes/current-state.md)。

## 交付

| 项 | 值 |
|---|---|
| 成品 ROM | CRC32 `8E7D8CC2`，内部校验和 `0x715F` |
| 补丁 | `kuniokun_cn.ips`（CRC32 `C242CD0F`），打在原版 `SF8127.smc`（CRC32 `56C05339`）上 |
| 已汉化 | 1013 条文本、560 条人名记录、选择框（是／否）、Start 菜单（气力／道具／装备／状态／扔掉） |
| 有意保留 | 标题 logo、制作人员名单、状态画面／HUD（按作者要求保持原版） |

## 构建

```bash
PYTHONHASHSEED=0 python cnbuild5.py          # 无环境变量 = 交付配置
```

需要 `work_kuniokun_2mb.smc`（原版 + 1 MB 零填充 + 3 个头部字节）作为构建基线，
原版 ROM 放在 `dl/roms/kuniokun__SF8127.smc`（**不入库**，见下）。

## 校验（每次构建后全跑）

```bash
python check16.py       # 文本 round-trip、字形池、人名记录
python verify16.py      # 65816 模型逐字节仿真绘制流程
python safe16.py        # 槽位/瓦片占用表
python checkband.py     # 提示表瓦片不在抽屉可达范围（彩色横条不回归）
python checkchoice.py   # 选择框 是／否 的脚本、字体位图、光标瓦片保护
python checkmenu.py     # 菜单标签指向字形池槽位 + 上传器接线
python test_stalerow.py # 残留行 stub 的边界用例
python test_menuclose.py# 菜单关闭时的清行 stub
python test_menuload.py # 用 65816 模型直跑菜单标签上传器
python ipsverify.py     # 交付 IPS 从原版重放 == 交付 ROM
```

## 目录

| 路径 | 内容 |
|---|---|
| `cnbuild5.py` | 构建器（唯一的构建入口） |
| `cn_translation.json` | 译文（按文本 ID） |
| `cn_build_params.json` | 最近一次构建的参数（校验脚本据此复现模块状态） |
| `kuniokun_map.py` | 字库/编码映射（FA/FB 表、码位） |
| `cnglyph.py` | 汉字点阵渲染（16×16 Unifont + 兜底） |
| `sim65816.py` | 65816 解释器 + PPU 模型（离线验证钩子用） |
| `prev_choice.py` / `prev_rom_cmdwin.py` | 从 ROM 直接渲染选择框 / 命令窗口 |
| `hw/*.lua` | EmuHawk 探针（驱动、VRAM dump、强制开菜单、A/B 截图） |
| `notes/` | 阶段状态记录 |

## 为什么仓库里没有 ROM

原版 ROM 与补丁产出的成品 ROM 都是受版权保护的游戏数据，**不入库**。
本仓库只放工具链、译文、逆向记录和交付补丁（`.ips`）；构建与校验都需要你本地自备原版 ROM。

## 授权与来源

逆向、构建器、译文与文档为本工程产出。游戏本身、字体（Windows 系统字体）与
模拟器（BizHawk / snes9x）版权归各自权利人，本仓库不含其二进制。
