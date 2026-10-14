# 优化版原基座重新汉化

2026-10-13，v2.0-rc2，CRC32 1F37BC30。由原优化 V4.1e（CRC32 65D66D5D）直接构建。
`optimized_port` 是旧汉化 ROM 的移植实验；v1.5 已有玩家正常流程乱码反例，留作历史，不参与这里的构建。
本工程复用项目审校译文、原编码知识和已经证明的各消费者接口，重新实现主消息读取与正文显存分配。

## 入口及输入

- `build_native.py`：唯一完整构建入口，检查私有输入指纹，生成零扩展原优化基座、锁定环境，再顺序执行两个构建阶段。
- `build_positional_components.py`：按目标优化表身份重配原译文，保留连续链，生成统一正文字形 ROM 及菜单／状态／名称组件。
- `patch_native.py`：主消息三字节表、原 loader／stream 钩子、三行正文槽分配、原六项菜单、国夫原版假名／其他人16×16 HUD 与状态名／状态词。
- `source/`：当前构建闭包，`cnbuild5.py` 是复用后适配的组件编译器。直接执行它只生成中间件，正文主入口还未接通，不能交付。
- `inventory-worker/`：优化原件五表及扩展表直接提取与输入验证；`candidate-translations.json` 是候选来源，`build_positional_components.py` 的少量人工裁定会覆盖失效或合并译文。
- `contracts-worker/`：原优化银行及接口字节锁。字节相等不等于全部动态语义已证明。
- `qa-static-worker/validate_native_text.py`：从候选真实三字节表独立读回及参数／控制边界审计，失败非零退出。
- `test_positions.py`：真实 65816 指令执行及队列模型，检查所有字形、三行滚动、行15→0、DE与正文混合、HUD隔离和满队列重试。

需要自备两份 ROM 及指纹一致的 `unifont.hex.gz`；私有素材不随源码提供。参数见 `inputs.json`、`dependencies.json`。

```powershell
python build_native.py --optimization "原优化版.sfc" --japanese "日版SF8127.smc" --font "unifont.hex.gz"
python qa-static-worker/validate_native_text.py
python test_positions.py
python verify_scope.py
python test_hud16.py
```

输出在 `new-build/native-rebuild-candidate.sfc`，4 MiB LoROM。兼容模拟器可读 banks40+ 字库。
`work_kuniokun_2mb.smc` 是保留的组件输入文件名，实际由此入口生成4 MiB原优化扩展基座，不是2 MiB汉化ROM。
干净源码目录＋三份私有输入独立重建须与发布SHA完全一致。默认候选不会自己升级为交付，不自动打包／提交／推送。

## 显示合同

固定 ROM 汉字存储每页128种。文本代码是 `[C0+page, glyph_id]`，动态姓名保留页内128以上的独立存储。
主消息 ID 是原表 index+1；原优化新增301..34B同表。300为空，348前导F3空边界保留。

正文、姓名、DE道具文本共用屏幕位置的显存槽：3条滚动行×13个16×16汉字位置。每行所属lane随原物理行变化轮转，不能用row%3，因为原行号16环回。
`03E5/03E6`仅属于新text-context lane/last-row，原E99D上下文清零和补丁写入由物理WRAM探针核对。`03E7`仍是节拍。
普通列表和状态页在各自生命周期使用原保留对表。HUD原绘制者分别写上下两行，支持完整16像素高字形；国夫用原版假名，力及敌人用16×16字形和独立瓦片，避免裁字及正文覆盖。
银行40低地址是ROM，不是WRAM镜像；队列写入用显式7E长地址，模型已修复该映射与直接页／栈相对bank0规则。

原优化20／22／23不搬家；唯一内部改动是20:909B菜单标签返回。514姓名记录只写前4字节，后12字节和尾部参数严格保留。
NPC在原七演员数组中照常存在；剧情同步等待原战斗结算，不删除NPC或强写门开标志。

## 运行证据

`run_mesen_native.py` 使用独立测试模拟器、复制ROM、验证检查点来源／输入不变，设置明确300秒内核超时，防止默认100秒退出被误认成死机。
用 `MESEN_EXE` 指定自己的核心路径；批量回归可用 `MESSAGE_STATE` / `STATUS_STATE` 指定同ROM检查点。`.lua`探针、`run_native_messages.py`和`run_native_status.py`需当前ROM冷启动检查点，不随源码分发任何状态文件。
`run_native_garage.py --prepare` 是显式受控剧情夹具；不是自然主线通关。按原演员初始化替换敌人记录与动作选择也只证明具名消费者。

按用户2026-10-13限定，原有汉化范围已收尾：1088条表内文本、514条姓名、菜单、状态、装备和选择框。`verify_scope.py`新增独立读回319条其他表项、15个状态标签，以及514条姓名×两块敌牌的原绘制调用。范围与证据见仓库 `notes/优化版重新汉化_v2.0-rc1_原有范围收尾_20261013.md`。存读档／命名UI、标题及额外图形不扩展；实体机、自然全流程、双人七演员全组合未验收。

2026-10-13 rc2：国夫显示原版「くにお」，力及敌人名牌完整16×16。两个核心确认上下半截可见，未修改HDMA。`test_hud16.py`从原HUD外层入口验证五档队列压力下保留更新及重试；`verify_hud16_pixels.py`核对实际VRAM和两核心截图笔画，需私有证据。详见 `notes/优化版重汉化_v2.0-rc2_HUD修复_20261013.md`。

## 补丁、变体和校对

- [正常rc2补丁](../../patches/optimized-v2.0-rc2/README.md)，目标CRC32 `1F37BC30`。
- [不掉血独立变体](variants/nohp/README.md)，目标 `E3C341ED`，不叠到正常构建。
- [离线校对工作台](../text_workbench/README.md)，修订稿是待合入提案，不自动改ROM。
- inventory-worker清单和候选是固定构建输入。重新提取会写回它们，属于新的分析操作；在独立副本使用附带的optimization-existing-cn.json和optimization-new-text.json，审查差异，不当作普通构建前置步骤。
