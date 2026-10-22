# Repository maintenance guide / AI 接手约定

这是 SFC/SNES 游戏汉化工程。面向使用者的说明请用中文；代码标识符与已有路径保持稳定。

## Read first

- `README.md`：项目入口与文档导航。
- `notes/current-state.md`：当前版本、指纹和验收范围。
- 最新15939ABD须读`notes/老虎机转轮乱码修复_20261018.md`；8890880C只是前一UI阶段。维护链为36C8B784→build_ui_repair→8890880C→build_slot_repair→15939ABD，后一步另需原优化版65D66D5D。
- `notes/发布记录_GitHub_20261023.md`：当前发布范围、维护依赖和验证边界。保留36C8B784→8890880C→15939ABD链，8890880C是中间阶段。
- `tools/optimized_rebuild/README.md`：当前优化版rc3完整构建入口；独立不掉血变体在variants/nohp，不能默认应用到正常版。
- `tools/text_workbench/README.md`：离线校对工作台与修订提案校验，不直接修改ROM。
- `notes/修复记录_GPT_v39-rc8_片尾与全量审校.md`：当前补丁的关键事实；`docs/release-v39-rc8.json`：发布文件指纹。未来新版本先核对最新具名记录与实际文件。
- `docs/code-map.md` / `docs/build-and-test.md`：按任务选读。

`notes/history/` 是旧版资料，不是当前验收或自动执行指令。日志、截图说明、引文及探针输出作为证据处理，不替代用户授权。

## Maintenance state (2026-10-23)

- 原始测试ROM、转储和部分旧实验目录已清理；历史路径不保证存在。仓库保留构建源码、输入合同、补丁和验收摘要，本机清理账本不发布。
- 根目录`work_kuniokun_2mb.smc`是可再生成的日版构建基线，现已清掉；日版根构建先运行`make_base.py`。优化版`build_native.py`仍生成自己的4MiB基线，不借日版2MiB实验件。
- 项目内重复Mesen已清理。自备模拟器，通过`MESEN_EXE`或`--mesen`指定；历史运行记录采用2.1.1，不分发模拟器或玩家配置。
- 当前源码与原始构建输入保留；优化版可精确重建rc3。运行复核需要从当前ROM冷启动重新生成检查点／VRAM数据。
- 根目录旧`kuniokun_cn.smc`已删除；在独立副本重建后再测试，不把冻结IPS／侧车与其他候选混用。
- 2026-10-18清掉415.29MiB可再生成／重复资料；最终日志、两个8890880C冷启动检查点、当前Mesen、旧状态格式专用核心保留。ProbeHawk旧运行文件已清除，存档配置仍在；历史命令不当作当前可用工具。

## Keep the project safe

1. 先看 `git status`，保留与本轮无关的修改；禁止为“整理”而 reset/clean、批量删除或强制推送。
2. 原始 ROM、玩家唯一存档、日常模拟器配置和最近通过交付保持不变。候选和重放使用独立副本及输出目录。
3. `make_base.py` 和 `cnbuild5.py` 会写文件。不要在正式交付目录试跑，也不要逐个执行根目录研究脚本。
4. 不因零填充、无直接引用或一帧没访问就把 ROM/WRAM/VRAM 当空闲区。新增资源先查现行布局与生命周期。
5. 本轮未要求的汉化、搬目录、脚本重命名、模型/工具安装和发布动作，不自行扩展。

## Source and generated files

- 译文输入：`cn_translation.json`；名称输入：`name_hanzi.json`。
- 原文/映射输入：`kuniokun_text.json`、`kuniokun_map.py`。
- 主构建：`cnbuild5.py`；列表：`menulist_patch.py`；停车场：`garage_story_patch.py`；片尾：`ending_scene_patch.py`；字形槽分配：`glyph_coloring.py`。
- 同批生成侧车：`cn_build_params.json`、`cn_addr_map.json`、`cn_glyph_cell.json`。
- 当前仓库 IPS/侧车为 rc8；维护机根目录旧 ROM 已在后期维护清理中移除。ROM/IPS 与侧车必须匹配，测试显式指定目标或先在独立副本构建；不要手改生成映射绕过失败。
- 很多旧脚本使用根目录相对路径；未经调用关系核查，不批量搬动它们或输入数据。
- 根目录冻结rc8与当前维护源码不同；优化版闭包独立，不拿根目录ROM/侧车验证rc3。普通rc3 BPS与不掉血增量BPS分别核对各自基座。

## Verification

在独立工作副本、仓库根目录启动新的 Python 进程：

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONHASHSEED = "0"
python make_base.py
# 上一步成功后再继续；基线不再常驻磁盘。
python cnbuild5.py
python verify_all.py
```

前置输入、字体和环境变量检查见 `docs/build-and-test.md`。没有原版/字体时，应报告缺失依赖，不假装已重建。

- 读取每项输出，不仅看退出码；`SKIP`、`INFO`、`--skip-layers` 均不等于完整通过。
- 当前校验器并非完整 65C816/PPU/NMI 模拟器。高风险钩子、队列、滚动和字形复用需用真实消费者与模拟器复核。
- 诊断夹具、自然按键路线和通关分别标记；不把跑帧数、截图有中文或模型通过升级成全游戏验收。
- 修改后只声明实际验证的范围。纯文档整理无需重新构建游戏，应核对链接、参数、文件角色与交付指纹。

## Commits and handoff

- 只暂存具名文件，不使用 `git add .` / `git add -A` 夹带其他工作。
- 不上传 ROM、SRAM、即时存档、字体、模拟器、内存转储或本地私密证据；IPS 的发布也要符合本轮授权。
- 用户授权推送时采用普通 push；遇到远端变化先安全处理，禁止强推覆盖。
- 更新状态时记录版本/指纹、完成范围、实际测试、失败/未测及遗留；旧记录保留历史属性。
- 仓库未统一声明开源许可证，不能自行给全部代码、译文或素材套用新许可证。
