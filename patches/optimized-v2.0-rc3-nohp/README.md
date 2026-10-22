# optimized-v2.0-rc3-nohp

2026-10-15完成并测试，2026-10-23同步仓库。保留普通rc3的270处修订，只增加独立不掉血变体；不能用于最新15939ABD维护件。

输入：**正常汉化 rc3（CRC32 403570B0）**。输出CRC32 **4AB9BCEA**，4 MiB。
SHA-256见[清单](release-manifest.json)。保留旧ROM和存档，更新后冷启动。

下载本目录BPS、清单和两个Python文件，在同一文件夹运行：

```powershell
python apply_patch.py "正确输入.sfc" --patch "optimized-v2.0-rc3-nohp.bps" --output "新ROM.sfc"
```

工具拒绝错源、错补丁和覆盖原件。[修订及验收](../../notes/优化版重汉化_v2.0-rc3_玩家修订_20261015.md)。
未实体机／自然全故事通关复测；不混用其他版本即时存档。
