# optimized-v2.0-rc2-nohp

独立不掉血变体：国夫和力受击不扣血，敌人正常伤害；受击动作仍保留。

- 输入：**正常优化版汉化 rc2（CRC32 1F37BC30，4194304字节）**。
- 输出CRC32：**E3C341ED**，4 MiB。源／目标／补丁SHA-256见[清单](release-manifest.json)。
- 本目录只发布BPS和应用工具，不提供ROM或字体。不能把两种BPS用在同一源上。

下载本目录四个文件（BPS、release-manifest.json、apply_patch.py、bps_codec.py）到同一文件夹，在该文件夹运行：

```powershell
python apply_patch.py "正确输入.sfc" --patch "optimized-v2.0-rc2-nohp.bps" --output "新的汉化ROM.sfc"
```

工具拒绝错源、错补丁或覆盖已有文件。请冷启动，保留旧正常存档；勿载其他版本即时存档。两核心具名验证和代码／回放校验通过，未实体机复测或自然全故事通关。

[不掉血变体验收](../../notes/优化版_rc2_不掉血hack_20261013.md)
