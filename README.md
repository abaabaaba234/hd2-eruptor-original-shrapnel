# HD2 Eruptor Original Shrapnel / 爆裂铳初版破片

Helldivers 2 的 R-36 爆裂铳模组，通过 **Bingus Shared Loader v18** 恢复初版的 **25 片高速破片**，每片 **300 普通 / 150 耐久伤害**，穿甲 **3/3/3/0**。

Restores the R-36 Eruptor's original 25 high-velocity fragments using Bingus Shared Loader v18. Each fragment has 300 normal / 150 durable damage and armor penetration 3/3/3/0.

## 下载与安装

[下载 v0.1.1 安装包](dist/EruptorOriginalShrapnel_v0.1.1.zip?raw=true)，在 Arsenal / HD2MM 导入 ZIP，启用模组与 v18 加载器，再 Purge / Deploy 并重启游戏。[完整中文说明](README_中文.md)包含加载器排序、配置与卸载方式。

支持的游戏版本为 **Steam build 25480438 / EXE 1.8.46015.0**。插件检查版本和数据签名；未知版本会停止写入。

本模组修改爆裂铳的破片类型和数量。主弹、爆炸伤害、爆炸半径及其他武器数据保持不变。复原的是初版破片配置，实际命中仍由当前游戏引擎处理。

## MODS 菜单

安装提供 **ModOptionsMenu version 2** 的菜单模组后，打开 Esc → MODS → **R-36 爆裂铳初版破片 / R-36 ORIGINAL SHRAPNEL**：

1. **Language**：选择“简体汉字”或“English”。菜单原生样式将英文选项显示为 `ENGLISH`。应用后关闭并重新打开 Esc 菜单以刷新文字；语言选择会保存。
2. **启用 / ENABLE**：开启或关闭效果。
3. **破片数量 / FRAGMENT COUNT**：1–64，默认 25。调整后点击应用。

没有菜单也可编辑 `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\EruptorOriginalShrapnel.cfg`：

```ini
enabled=1
count=25
language=zh
```

`language=en` 使用英语；`enabled=0` 恢复修改前的破片配置。

## 构建与验证

Python 3.12 与 LuaJIT 2.1（由 `lupa` 提供）：

```powershell
python -m pip install -r requirements-dev.txt
python tests/test_runtime.py
python tools/build.py
```

输出位于 `dist/`。离线验证报告为 [validation/report.json](validation/report.json)，已通过 17 组测试，包括数据恢复、写入回滚、语言保存及菜单顺序。

其中真实菜单接口测试需要本地的 ModOptionsMenu Lua 源码，第三方源码不随此仓库分发。可将源码放在 `research/references/mod_options_menu_9ba626afa44a3aa3.patch_15.lua`，或通过环境变量 `HD2_MOD_OPTIONS_MENU_SOURCE` 指定路径。缺少源码时只跳过这一组集成测试，其余测试照常运行。真实游戏启动、战斗与联机效果不由这些离线测试覆盖。

历史配置与偏移证据见 [RESEARCH.md](RESEARCH.md)，第三方来源见 [CREDITS.md](CREDITS.md)。原始游戏文件、共享加载器与第三方模组源码不包含在仓库或安装包中。
