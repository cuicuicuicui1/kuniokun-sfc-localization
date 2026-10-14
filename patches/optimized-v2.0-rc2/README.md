# optimized-v2.0-rc2

原优化版直接重汉化，含新增台词、菜单、状态、道具、地名和HUD修订。

- 输入：**原未汉化优化版 V4.1e（CRC32 65D66D5D，1572864字节）**。
- 输出CRC32：**1F37BC30**，4 MiB。源／目标／补丁SHA-256见[清单](release-manifest.json)。
- 本目录只发布BPS和应用工具，不提供ROM或字体。不能把两种BPS用在同一源上。

下载本目录四个文件（BPS、release-manifest.json、apply_patch.py、bps_codec.py）到同一文件夹，在该文件夹运行：

```powershell
python apply_patch.py "正确输入.sfc" --patch "optimized-v2.0-rc2.bps" --output "新的汉化ROM.sfc"
```

工具拒绝错源、错补丁或覆盖已有文件。请冷启动，保留旧正常存档；勿载其他版本即时存档。两核心具名验证和代码／回放校验通过，未实体机复测或自然全故事通关。

[HUD修复及验收](../../notes/优化版重汉化_v2.0-rc2_HUD修复_20261013.md)
