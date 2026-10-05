# 源码导航：先认入口，再认文字消费者

[返回首页](../README.md) · [构建与测试](build-and-test.md)

## 推荐阅读顺序

1. [当前状态](../notes/current-state.md) 与 [rc8 修复记录](../notes/修复记录_GPT_v39-rc8_片尾与全量审校.md)；战斗 HUD／列表再查 rc4 记录。
2. `cnbuild5.py` 的 `main()`：译文控制结构对齐、编码/字形布局、写入数据、安装钩子、校验和与 IPS。
3. 根据窗口定位到对应 renderer，不先全库扫描或试跑所有旧脚本。
4. 找对应 `test_*.py`、`check*.py` 和 `hw/*.lua`；确认它实际执行哪一级调用链。

## 日常维护的文件

| 类别 | 文件 | 说明 |
| --- | --- | --- |
| 主要入口 | `make_base.py` | 从正确原版生成扩展基线，会写文件 |
| 主要入口 | `cnbuild5.py` | 当前构建入口；文件名中的“5”是历史设计编号，不是发布版本 |
| 补丁组件 | `menulist_patch.py` | 气力/道具动态列表的队列绘制器，由构建器调用，不单独构建 |
| 译文输入 | `cn_translation.json` | 按文本地址索引的译文，包含控制码占位；修改须保结构 |
| 原文输入 | `kuniokun_text.json` | 原文本记录、地址与指针表信息 |
| 名称输入 | `name_hanzi.json` / `name_hanzi.csv` | 名称映射与人类可读对照 |
| 编码工具 | `kuniokun_map.py` | 原字符编码、瓦片映射等 |
| 字体工具 | `cnglyph.py` / `cnfont8.py` / `pixelfonts.py` | 不同字号的渲染、字体读取与像素处理 |
| 生成工具 | `sfc_tools.py` | 2bpp 打包、IPS 生成 |
| 生成侧车 | `cn_build_params.json` | 实际参数/保护区/布局，用于解释对应 ROM |
| 生成侧车 | `cn_glyph_cell.json` / `cn_addr_map.json` | 字形位置与文本回插地址，不是译文输入 |
| 检查总入口 | `verify_all.py` / `build_context.py` | 必测列表与临时测试副本 |
| 模型 | `sim65816.py` | 有限的 CPU/总线/PPU 模型，不是完整模拟器 |
| 补丁检查 | `ipsverify.py` | 重放 IPS 与选定 ROM 逐字节比较 |
| 真实运行 | `tools/`、`hw/` | 无头工具、模拟器探针、路线与诊断夹具 |

`cn_translation.backup.json`、旧 `cnbuild*.py`、根目录探针/截图属于历史或研究材料，不因文件名相似就成为新构建依赖。以当前入口实际读取的文件为准。

## 同一汉字，可能有不同的绘制路径

| 画面消费者 | 关键阅读入口 / 证据 | 不能混淆的地方 |
| --- | --- | --- |
| 正文/剧情/战斗消息 | `cnbuild5.py` 的编码、drawer 与 tick；`verify16.py`、`test_pace.py` | 页码、控制码、上传节拍、换行与前一条消息残留 |
| 对话说话人标签 | 构建器的名称记录/标签路径；`check16.py` | 标签分组和消息生命周期，不是活动战斗名牌 |
| 战斗 HUD 敌人名字 | HUD 补丁；`test_hudname.py`、`test_runtime_names.py` | 上下字形顺序、私有瓦片、外层预留、dirty/retry |
| Start 静态菜单标签 | 菜单上传器；`checkmenu.py`、`test_menuload.py` | 打开菜单后固定标签，不等于气力/道具内容列表 |
| 气力/道具动态列表 | `menulist_patch.py`、`test_menulist.py` | 原加载器、两行字形所有权、持续滚动、NMI 队列回收 |
| 消息插入道具名 | drawer `$DE` 真入口；`test_runtime_names.py`、`test_itemmsg.py` | rc6完整16×16左右半字、两列/换行/索引槽位；状态页8×16另行保持 |
| 状态页标签/装备值 | 标签/道具 renderer；`test_labeldraw.py`、`test_itemdraw.py` | 8×16 字形、状态脚本与其他场景字体保护 |
| 字框下缘点/文字裁切 | `install_text_window_alignment()`、`test_text_band.py`、`tools/check_text_band_pixels.py` | rc6纵向偏移减1、32扫描线完整两行；不等同于底边横向漂移 |
| HP 与边框图形 | `test_hud_tiles.py`、`test_pace_hdma.py` | 非文字瓦片、原调色板与 HDMA 表不能被文字资源覆盖 |

修乱码先确认真实消费者，再查编码/字形/上传/引用的哪一跳出错。修改一个公共文本分支，不代表 HUD、状态页与列表自动一起修好。

## 当前构建的几个定位点

以下仅是本游戏 rc8 的定位提示，不是可推广的 SNES 通用规则：

- 正文字形池：bank `$20` 起，30 页至 `$3D`，正文槽位 33。
- 战斗 HUD 私有配对表：ROM 文件偏移 `0x1F0780`。
- 动态列表 renderer：ROM 文件偏移 `0x1F6000`。
- 动态列表道具 16×16 字库：ROM 文件偏移 `0x1FA000`。
- 打字倒计时：WRAM `$03E7`；旧 `$03C4` 位于 BG3 HDMA 表，不能挪回去。

文件偏移、CPU bank:address、WRAM、VRAM 字节/字地址和 tile 编号分别标注，不把它们直接互换。构建器开头部分历史注释或预设常量不一定等于 `main()` 最终计算布局；复核对应 ROM 的 `cn_build_params.json` 和具名修复记录。

## 如何看待旧研究材料

根目录保留较多旧脚本、PNG、TXT、TSV，用于追溯字库、指针和图形实验。它们可能依赖个人路径、旧 ROM 或旧模拟器 API，并不统一支持 `--help`，也不保证只读。

- 不批量运行脚本来“发现入口”。
- 不把截图、文件名或一次零命中当成完整运行证据。
- 不在未查调用关系前搬动代码和数据。
- 历史教程/交接集中在 [notes/history](../notes/history/README.md)，按当前修复记录纠正旧判断。

## 列车 / 文本队列所有权（2026-10-02 新反例）

文本队列的 DD、DF 都是 **单字节**游标：`$09DE` 属于另一图形队列，`$09E0/$09E1` 是原 `$00:FC75` 产生的带符号列车位移，不是文字游标高字节。任何 16 位 LDX/STX 或 LDA/CMP 必须明确隔离邻字节；不要通过“高字节非零就等待”规避问题，也不要在模型里一起清零 DD..E0。

工作树的 `Asm.queue_load_x` / `queue_store_x`、`test_train_queue.py` 和 `hw/mesen_train_queue_fixture.lua` 处理并检验此边界。详见 [queue-test 记录](../notes/修复记录_GPT_v39-rc5_queue-test.md)；该机制记录只证明局部消费者对照；完整梅田具名回归与边界见下节及 rc8 记录。

## 梅田战后原事件回归（2026-10-02）

`$1D22/$1D23`是待启动/运行事件，`$1D20/$1D21`是bank04脚本PC；事件08的战后奖励在`$04:A3BA`启动message0005。旧DE消费者等待09E0导致原VM停于A3BE；新候选通过。`hw/mesen_umeda_jump.lua`受控准备原事件，`hw/mesen_umeda_continue.lua`零内存写入续跑，`tools/run_umeda_story.py`封装同ROM重放和身份保护。详见[梅田剧情验收](../notes/修复记录_GPT_v39-rc5_梅田剧情验收.md)；不等同于自然救援/通关。


## 停车场战后交接（rc7）

`garage_story_patch.py`由`cnbuild5.py`显式安装；原`07:8E1A`只在地图4B、event95、VM=B94B的最终零人数等待中，额外等原战斗/结算/spawn全0。人数为0不能代表原F57E结算清理完成，否则清理会抹掉随后剧情刚设置的玩家移动锁，原B98E移动等待不完成、B9D4撤95未执行。

代码保留页ROM`1F5C00..1F5D00`，71字节；没有新WRAM变量，不写NPC或门锁。`test_garage_sync.py`跑真实原消费者与32例ABI/范围合同，并拒绝错hook和占用保留页。前置受控、跨ROM诊断与同ROM具名验收分别见[rc7记录](../notes/修复记录_GPT_v39-rc7_停车场剧情交接.md)。这些地址只适用于本游戏此基座。

## rc8新增组件（2026-10-03）

- `glyph_coloring.py`：只接收真实共显窗口，确定性核心求解/稀疏扩展/容量检查；不推断生命周期，不借VRAM。`test_glyph_coloring.py`覆盖固定码、容量、团与奇环负例。
- `ending_scene_patch.py`：代码页1F5D00..1F5DFF；限eventAC/map27/FEB8清残留DE1/DE2；原opcode51 JSL和普通F6不改。`test_ending_scene.py`覆盖162个ABI/范围案例及native flag20反例。
- `test_credits_text.py`：30完整罗马字署名、20真实片尾共显集合、全来源窗口/列容量独立重建、F2F6宏对齐。
- `notes/text-review-v39-rc8.json`：1013条日文/旧中文/审校中文与理由，**是审校证据，不是新的构建输入**。构建仍只读取`cn_translation.json`。
- STATUS道具显示使用现有左右pair表24/30/36三组六列；对白暂停，不与静态标签/原raw字段/永久战斗HUD共享活瓦片。
