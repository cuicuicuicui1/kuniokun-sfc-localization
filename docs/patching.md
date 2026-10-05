# 补丁使用说明

[返回首页](../README.md) · [当前版本与指纹](../notes/current-state.md)

## 需要什么

- 仓库根目录的 `kuniokun_cn.ips`（当前 v39-rc8；补丁 SHA-256 见当前状态）。
- 自己合法取得的**无外部头日版原 ROM**：1,048,576 字节，CRC32 `56C05339`。
- 能应用 IPS 的工具，以及 SNES 模拟器。它们不随仓库提供。

不要使用旧汉化 ROM、已经改版的 ROM 或带 512 字节外部头的 dump 作为输入。

## 使用步骤

1. 备份原版与游戏内 SRAM 存档，复制一份原版用于应用补丁。
2. 核对原版 SHA-256：

   ```text
   8f289ac5677508f7c9de12a0117849ed55a0ac861abb0fcefb1e350af6978c04
   ```

3. 将 `kuniokun_cn.ips` 应用到原版副本，不覆盖唯一原件。
4. rc8 结果应为 **2,097,152 字节**、CRC32 **`BD76DCA1`**；SHA-256：

   ```text
   160243a6fc0e9077a682fd5e134d1be5a2743a74acea61ab87d00f4a0b647bef
   ```

5. 关闭旧 ROM，重新打开新 ROM、冷启动。不要加载旧版本的模拟器即时存档。

PowerShell 可核对文件大小和 SHA-256（把示例路径换成实际文件）：

```powershell
(Get-Item -LiteralPath "原版副本.smc").Length
Get-FileHash -LiteralPath "原版副本.smc" -Algorithm SHA256
Get-FileHash -LiteralPath "汉化结果.smc" -Algorithm SHA256
```

若有 Python 和仓库源码，可以额外核对补丁重放：

```powershell
python ipsverify.py --original "原版副本.smc" --ips kuniokun_cn.ips --rom "汉化结果.smc"
```

该命令只比较 IPS 重放与指定目标是否相同；**不能替代前面的原版及目标指纹检查**。

## 存档和黑屏提醒

- 普通游戏内 SRAM 与即时存档不是一回事。更新时先备份普通 SRAM，不要自动删除。
- 旧即时存档可能保留旧指针、VRAM 或错误滚动量，不能用来验收新补丁。
- 曾在用户的 Snes9x 1.63 环境中复现“声音同步 / Sound Sync”开启导致启动黑屏、关闭后可启动。这只是那一环境的绕过记录，不是所有黑屏的通用原因。
- 遇到问题先核对实际加载的 ROM 指纹，并冷启动；不要在未确认原因前清空存档或修改全部模拟器设置。

当前还有残留日文与未覆盖场景，见 [当前状态](../notes/current-state.md)。报错最好提供 ROM CRC/SHA、模拟器版本、是否冷启动、窗口类型和截图；战斗 HUD、对话名字、气力列表、道具列表请分别说明。
