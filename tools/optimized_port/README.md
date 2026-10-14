# V4.1e 操作优化版的汉化移植

> **历史实验，已停用。** 玩家正常流程截图证明v1.5仍有乱码，原整体可用结论失效。当前路线是直接从原优化版重汉化的 [optimized_rebuild](../optimized_rebuild/README.md)。以下仅保留旧分析方法与当时记录，不用于生成现行rc2。

这是与日版 rc8 发布分开的适配入口。固定优化输入 CRC32 65D66D5D、20261010 汉化基座 38FA572A、干净日版 56C05339；本地 v1.5 目标 B4405973。不能把旧版本补丁直接叠上。

已识别改动：6248 原银行字节、1019 原银行区间和 1339 总区间。46 个原 Hook 进入新代码；854 条可达指令、98 个搬移引用。构建会校验真实 514 条人物表边界和姓名以外的参数，拒绝未知 ROM 指纹或新增资源。

## 源码角色

build_port.py 是增量合并与重定位，patch_ui.py 是 UI/玩家 HUD 适配。optimization-cn-text.json 为 75 条新增译文，optimization-existing-cn.json 为 25 条旧消息覆盖，原文见 optimization-new-text.json。diff-analysis.json 是固定输入和差异区间，不把 notes 的旧完成度当输入。

runtime_paths.py 解决代码/模拟器路径；dependencies.json 固定私有 Unifont 和系统字体。字体资源不在仓库。relocation_decoder.py 跟踪真实分支/宽度，audit_native_hooks.py 校验原 Hook opcode 和目的地，test_payload_integrity.py 独立核对整块代码/数据。check_code.py 汇总静态与 CPU/队列模型，Mesen/Snes9x 记录分开。

## 从仓库复建

在此目录的独立工作副本运行，源码树指定副本的仓库根。Python 3.12/Pillow，提供自己的三个 ROM 和匹配的 Unifont；配置器不会下载依赖或修改原 ROM。

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONHASHSEED="0"
python configure_inputs.py --jp "日版.smc" --opt "优化版.sfc" --cn10 "20261010汉化版.sfc" --unifont "unifont.hex.gz" --source-tree "仓库根目录"
$env:SFC_RECON_SOURCE="仓库根目录"
python build_port.py
python patch_ui.py
python check_code.py
```

日版需在源树 dl/roms 下供旧读取器使用。configure_inputs.py 只在缺失时复制已经通过指纹校验的私有日版，拒绝覆盖不同文件。请使用独立工作副本，不向公开包加入该私有文件。运行生成 candidate*.sfc 和 JSON/日志，均不作为仓库发布输入。

## 运行测试与边界

私有 Mesen 由 SFC_MESEN_EXE 指定，运行器可由 SFC_MESEN_RUNNER 指定。先用候选冷启产生它自己的 final-cold 检查点，再运行消息/状态脚本，禁止跨 CRC 加载。

v1.5 本地记录见 ../../notes/优化版移植_v1.5_代码复审_20261012.md。复核 15 个动态词的字库共显关系；1F6 增加分页；保持旧/新字库切换走原 F0 异步清页。L+R+X 属性调整和菜单互伤开关是两条独立路径。既有旧修复保留，未声明自然通关、实体机、具体新增敌人全部场景或旧存档迁移通过。


最后检查：新增 test_crowded_consumers.py（3276 个外层 HUD 队列案例和 748 个交错正文/道具上传，保护七槽演员与剧情数组），由 check_code.py 调用。复杂环境运行范围和未通过的人工双人进门实验见 ../../notes/优化版移植_v1.5_收尾验收_20261012.md。本轮 ROM 字节未改变。
