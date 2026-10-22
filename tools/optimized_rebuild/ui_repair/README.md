# 外部修订版的 UI 维护补丁（2026-10-18）

**最新转轮反馈修复：目标15939ABD。** 下述8890880C是保留的上一阶段入口；它只补是／否，未补原老虎机图案。维护时接着执行`build_slot_repair.py`，或使用[直接BPS](../../../patches/optimized-rc3-slot-20261018/README.md)。[原因与验证](../../../notes/老虎机转轮乱码修复_20261018.md)。

```powershell
python build_slot_repair.py "UI版8890880C.sfc" --optimization "原未汉化优化版65D66D5D.sfc" --output "转轮修复15939ABD.sfc" --report "转轮修复.json"
python test_slot_repair.py --base "UI版8890880C.sfc" --rom "转轮修复15939ABD.sfc" --optimization "原未汉化优化版65D66D5D.sfc" --report "转轮模型验证.json"
```

新写入器固定输入SHA、输出SHA、原老虎机消费者及空白扩展地址；拒绝重复打补丁。入口使用220字节原队列完整事务，补原tile4A..51和53，保留52归STATUS使用。模型、Mesen和玩家Snes9x原流程分别验收。

针对用户提供的 `初代热血硬派_优化版汉化_v2.0-rc3_20261017_修订版.sfc`，CRC32 **36C8B784**。它与源码普通 rc3 的 `403570B0` 不同；新增的外部台词编辑完整保留，不拿旧译文表覆盖。

`build_ui_repair.py` 是这份冻结输入的独立、可重现末级写入器，不改变既有 `build_native.py` 的历史目标。字体使用既有 Ark Pixel 12px zh_cn BDF，五个缺字在源码中显式补点阵。原 ROM、字体、存档、模拟器均不上传。

```powershell
python build_ui_repair.py "外部修订版.sfc" --font "ark-pixel-12px-monospaced-zh_cn.bdf" --output "修复版.sfc" --report "修复清单.json"
```

输出 CRC32 **8890880C**，SHA256 `47685520673b973b8337e3235f299fdeda5805054b4031b2a0f154b4d2da5936`，4194304 字节。错误底稿、字体变化、已打补丁的 ROM、已存在输出会报错。

- `ui_display_patch.py`：选择框第一行以原队列预留 208 字节，先补回“是／否”字形，再绘原字框；忙时原行重试，不写相邻列车变量。
- `status12_patch.py`：状态页 15 处标签、两个人名、三种状态词、110 个道具名以及空装备统一 12px 字距，专用显示条带复用暂停时字库槽；数字、头像和菜单操作由原程序负责。
- 代码 ROM `186100`、`186800`；STATUS 资源 `1A0000`，位于优化版未使用、4MiB扩展的声明区段。只写入核对为全零的指定范围，并固定输入 SHA；不据此推断其他 ROM 的空白区可用。
- 三个 STATUS 入口使用原强制消隐阶段，未分配私有 WRAM；72 对字块与战斗 HUD 隔离。静态标签共用相同像素切片，三个六字装备栏分别有完整的九列空间。
- 原主表指针／台词 `184100..185FFF`、`188000..18FFFF` 和外部参数 `1F582A` 逐字节不变。战斗 HUD、正文、其他菜单、玩法代码不改。

具名测试、受控显示参数与未测范围见仓库 `notes/优化版_UI修复_20261018.md`。无头模拟器测试不等于实体机或全剧情通关。
