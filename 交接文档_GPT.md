# 维护交接

2026-10-15。先核对[当前状态](notes/current-state.md)和Git状态，再选路线。仓库同时保留三个目标，不混用基座、补丁或即时存档。

| 路线 | 构建入口 | 目标CRC32 |
| --- | --- | --- |
| 当前优化版rc2 | tools/optimized_rebuild/build_native.py | 1F37BC30 |
| 独立不掉血版 | tools/optimized_rebuild/variants/nohp/make_nohp.py，输入正常rc2 | E3C341ED |
| 日版冻结rc8 | 根目录IPS／三份侧车冻结；根维护源码已有后续更改 | BD76DCA1 |

## 最短接手顺序

1. [AGENTS.md](AGENTS.md)、[当前状态](notes/current-state.md)。
2. [优化版源码说明](tools/optimized_rebuild/README.md)、[rc2 HUD修复](notes/优化版重汉化_v2.0-rc2_HUD修复_20261013.md)。
3. [补丁应用](patches/optimized-v2.0-rc2/README.md)、[验收JSON](notes/优化版重汉化_v2.0-rc2_HUD验收.json)。
4. 做文本校对时读 [工作台](tools/text_workbench/README.md)，修订稿先校验为提案，再合入真实候选／扩展表／姓名输入。
5. 处理日版历史时读 [rc8记录](notes/修复记录_GPT_v39-rc8_片尾与全量审校.md)、[源码导航](docs/code-map.md)和[构建文档](docs/build-and-test.md)。

## 当前合同

- 原优化V4.1e输入65D66D5D，生成4MiB；主消息index+1、扩展301..34B，300空边界，348前导F3保留；连续链不合并成错误终止。
- 正文、姓名和DE共用3滚动行×13列位置槽；03E5/03E6是上下文lane/lastrow，03E7是节拍。物理行16环回，不能直接row%3。
- 国夫HUD原版「くにお」；力／双敌牌16×16，独立瓦片，完整队列预留／忙时重试。不要恢复“HUD只有8像素高”的旧假设。
- 514人物记录只改前4字节姓名；后12字节和表后参数保留。队列09DD/09DF单字节，09DE和09E0/09E1不是高字节。
- 停车场保留NPC和原结算／移动／开门；片尾只限定eventAC清旧列车状态，禁止恢复phase80原型。
- 既定汉化范围1088文本／514姓名，菜单状态等既有路径；不追加存读档、命名键盘、标题或额外图形。

## 证据和未测

所有声明绑定ROM SHA，受控显示／剧情夹具、CPU模型、自然按键和硬件分别标记。[当前状态](notes/current-state.md)列出验收。未自然全故事通关／实体机复测／七演员双人组合穷举／旧正常存档兼容。

旧optimized_port/v1.5有玩家反例，仅作历史，不参与rc2构建。根目录冻结日版rc8不是优化版回归目标；root cnbuild5.py的后续边界修正不冒充旧冻结产物。

校对工作台可直接分享HTML；暂存是浏览器本机数据，必须导出JSON才会带上修改。代码／DOM模型及修订文件验证通过，实际浏览器视觉尚未验收。不要把校对提案当成已经回插的ROM。

独立副本构建，不写玩家唯一存档、日常模拟器配置或可用交付。发布只包含具名源码、BPS、离线工作台和摘要；不上传ROM、字体、模拟器、状态和原始媒体。
