# 爆裂铳初版破片 v0.1.1

需要 **Bingus Shared Loader v18**。目标游戏为 Steam build **25480438** / EXE **1.8.46015.0**。

默认恢复 **25 片高速破片**，每片 **300 普通伤害、150 耐久伤害**，角度穿甲为 **3/3/3/0**。使用游戏仍保留的初版 `Shrapnel_High_Velocity` 弹体：初速 1000 m/s、质量 2 g、寿命 2 秒。其伤害定义与轨道空爆破片一致；它不是空爆火箭的小炸弹，也不带目前轨道重破片的二次爆炸。

本插件只修改爆裂铳爆炸记录中的破片类型和数量。主弹伤害、爆炸伤害与半径、射速、弹匣，以及现行引擎的破片散布和碰撞规则均保留。因此它复原的是初版破片配置，不能宣称完全重现 2024 年的武器行为或击杀效果。

## 安装

1. 关闭游戏，在 Arsenal / HD2MM 导入 `dist/EruptorOriginalShrapnel_v0.1.1.zip`，替换旧版。
2. 启用本插件和已有的 v18 加载器。
3. **停用“爆裂铳破片向前 v2.3”**。两者同时运行会争用破片配置；本插件检测到它后会停止并写日志。该模组仅作为结构和菜单接口参考。
4. 按 v18 文档排序：Arsenal 默认优先级下加载器放最下方；如果启用“第一个 mod 优先”，则放最上方。
5. Purge，然后 Deploy，重启游戏。

不需要把 Lua 源码手动放进游戏目录。ZIP 中的 `Addon` 归档带自动发现声明，v18 会载入 `mods/eruptor_original_shrapnel/core`。

## 数量与开关

默认 **25**，为 2024-04-16 数据快照中的初版数量；当前原版为 **30**。

配置文件：`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\EruptorOriginalShrapnel.cfg`。

```ini
enabled=1
count=25
language=zh
```

`enabled=0` 恢复本插件修改前的破片字段。`count` 支持整数 1–64，保存后约一秒读取；恢复初版时设为 25。设为 30 仍使用初版高速弹体，不等于恢复当前原版。

如果另外安装了提供 `ModOptionsMenu` 的 Vanilla Plus Megapack，MODS 页会出现本模组的按钮，默认名称为 **R-36 爆裂铳初版破片**，英语下为 **R-36 ORIGINAL SHRAPNEL**。语言控件需要支持动态文字的 ModOptionsMenu version 2。

打开本模组后，第一行是 **Language**，两个选项为 **简体汉字** 和 **English**。选择语言并按菜单的“应用”操作，然后关闭并重新打开 Esc 菜单，模组按钮、启用开关、数量标签与说明会切换语言。菜单原生样式会将英文选择文字显示为大写 `ENGLISH`。

默认简体汉字，`language=zh`；英语为 `language=en`。选择会保存到上述配置文件，重启后保留。旧版配置没有语言键时自动使用简体汉字，保留原有的数量和开关设置。本选项仅改变这个模组的文字。

第二行“启用 / ENABLE”控制效果，第三行“破片数量（初版 25） / FRAGMENT COUNT (original 25)”支持 1–64 片。改完后同样需要应用。菜单可选，没有它也能通过配置文件运行。

日志：`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\EruptorOriginalShrapnel.log`。正常生效后有 `Active:25 high-velocity fragments`。仅加载成功不代表战场效果已验证。

## 验证与限制

已在 LuaJIT 离线运行实际插件，检查默认配置、数量切换、禁用恢复、其他武器数据不变、指针变化、冲突、写入失败与回滚、页面保护、更新回调和管理器 ZIP 结构。结果见包内 `VALIDATION.json`。

离线测试没有验证真实游戏启动、战斗效果或联机同步，具体覆盖范围见 `VALIDATION.json`。

恢复旧高速破片后，初版破片的高伤害会同样作用于友军。实际命中片数仍受当前引擎、距离、地形与护甲影响，不能把 25×300 当成每次射击必中的伤害。

不再使用时，禁用插件，Purge / Deploy 并重启游戏。若检测到其他写入者或记录移动，插件会拒绝覆盖，以日志为准；重启进程可完整恢复原版数据。

## 开发

源码 `src/core.lua`。使用 Python 3 和 `lupa` 的 LuaJIT 2.1 后端运行 `python tests/test_runtime.py`，然后 `python tools/build.py`。来源与偏移验证见 `RESEARCH.md`；仓库首页说明开发依赖与可选的真实菜单测试。
