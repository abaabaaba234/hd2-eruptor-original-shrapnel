---
name: hd2-mods-menu
description: "将 Helldivers 2 Lua 模组的可调参数适配到 Bingus ModOptionsMenu 的 MODS 页面，包含开关、滑块、选项、中英语言切换与配置持久化。用于新增或修改模组菜单控件，不用于原生菜单提供者开发或其他游戏的设置页。"
---

# HD2 MODS 菜单适配

将现有模组的配置接入 `_G.ModOptionsMenu`，让用户在 MODS 页编辑参数；继续使用模组自己的校验、保存和生效路径。以下接口依据实际部署的 API1 / version2 菜单和爆裂铳初版破片 v0.1.1 验证。

## 先确认现有实现

- 查找模组的配置读取/保存、参数校验、更新回调、恢复逻辑，以及已有 `register_option` / `on_change` 调用。保留用户已有的字段名、默认值、数值范围和行为；示例中的数量 1–64、默认 25 只属于爆裂铳。
- 区分 **Bingus Shared Loader** 与 **ModOptionsMenu**。加载器负责运行 Lua，MODS 菜单来自另外安装的菜单模组；不要把 v18 加载器描述成自带菜单。
- 检查当前菜单的真实 API/源码，搜索 `register_option`、`on_change`、`get`、`set`、`translation.refresh`、`api.version`。有本地文件优先读取；版本不同则核对能力再适配，不把这次观察当成所有未来版本的保证。
- 详细语义及常见陷阱见 [references/mod-options-menu.md](references/mod-options-menu.md)。需要实现模板时读取 [assets/mods_menu_adapter.lua](assets/mods_menu_adapter.lua)；它是可内联的 Lua 示例，无游戏内存操作。

## 参数接入

为每个参数分配稳定、全局唯一的 ID，例如 `my_mod_enabled`、`my_mod_count`。不要随语言变化改 ID，也不要使用其他模组的前缀。传相同的 `mod` 来源函数使控件归入同一个模组。

| 参数 | 控件 | 应用值 |
| --- | --- | --- |
| 开关 | `type='toggle'` | boolean；`false` 不能用 `or default` 覆盖 |
| 有界数值 | `type='slider'` | number；提供实际 `min/max/step/default` |
| 有限枚举、语言 | `type='choice'` | **从 1 开始的索引**；映射到配置内部值 |

按希望显示的顺序注册一次；不要逐帧注册或重复添加回调。菜单可晚于当前模组加载，因此菜单尚不存在时允许在后续更新中再尝试。保留原有 `update(...)` 链与返回值，沿用模组已有的更新调度。

`on_change` 在用户点击“应用”后调用。回调校验值、更新配置并保存，再通知既有生效路径处理参数变化。不要新建另一套绕过原有保护的游戏写入逻辑；禁用仍走已有恢复逻辑。检测并记录注册或回调绑定失败，菜单失败不应阻止独立的配置文件功能。

先加载并校验配置，再注册默认值。选择一个持久化权威来源；对已经使用独立配置文件的模组，沿用配置文件作为权威。注册后及外部配置改变后同步菜单；只有 `menu.get(id) ~= wanted` 时才调用 `menu.set(id,wanted)`。不要每帧无条件 set，它会丢弃用户尚未应用的编辑。`set` 不触发回调；改动生效由配置读取/应用流程负责。

## 中英语言选项

此技能的默认菜单方案是在 **本模组的第一行** 注册 `Language`，保持该标签不翻译：

```lua
{type='choice', label='Language', mod=title,
 choices={'简体汉字','English'},
 default=config.language=='en' and 2 or 1,
 description=text('language_description')}
```

- 配置保存 `language=zh` / `language=en`，索引 1/2 映射到这两个值。新增字段时保留旧配置的其他参数；缺少语言字段默认 `zh`，不重置整个配置。
- 为模组标题、参数标签和说明提供中英文文本，并通过 **函数**返回当前语言文本。API version2 会在 Esc 菜单重新打开时调用这些函数；一次性传字符串或重复注册无法替代动态文本刷新。
- 语言回调只修改、保存语言配置。用户点击应用后关闭并重新打开 Esc 菜单，再观察标题、标签和说明变化；不要声称当前菜单即时重绘。
- 该菜单会把 choice 文本转成大写，`English` 实际显示为 `ENGLISH`；传入的文本仍为用户要求的 `English`。需要精确保留大小写时，先检查菜单提供者是否支持，不擅自改动它。
- 语言选择只影响这个模组，不改游戏全局语言、`BingusTranslations` 或其他模组的文字。

## 使用模板

将示例文件内容内联到现有核心 Lua，在配置初始化后实例化一次：

```lua
local menu = create_mods_menu_adapter{
    namespace='my_mod',
    get_config=function() return config end,
    save_config=save_config,
    request_apply=function() elapsed=1 end,
    log=log,
    titles={zh='我的模组', en='MY MOD'},
    count={min=1, max=64, step=1}, -- 换成目标参数的实际范围
}
-- 在已有更新路径中，读取有效配置后调用 menu.step()。
```

模板约定 `enabled` 为 0/1、`count` 为有效数值、`language` 为 zh/en；这是示例配置，不是 API 的限制。为别的参数修改字段映射、标签、范围和校验；纯开关或枚举模组可删减数量示例。用 `get_config` 获取当前配置，避免配置读取替换整个表后模板还持有旧表。

## 验证与交付

验证显示顺序、正确默认值、旧配置迁移、点击应用后的保存、重启后保持选择，以及语言来回切换。保留有业务意义的现有测试；针对缓存覆盖、未应用编辑、重复回调和非法值等实际边界进行检查。可用 LuaJIT 和模拟 API 做离线测试，有真实菜单源码时可运行其注册/保存 API，避免调用本机游戏 UI 或 native hook。

无菜单或菜单版本不支持时，检查配置文件路径仍可使用。验证语言更改不改业务参数，并检查原有禁用恢复行为。只把实际做过的游戏内测试报告为实测。

更新使用说明，明确菜单来源、语言刷新操作、参数范围和配置位置。若任务要求安装包，按该模组已有打包方法重新构建，检查实际归档内 Lua 与源码一致，并且保留 v18 的 `-- HD2-Addon: mods/...` 自动发现声明。菜单逻辑变化本身不需要重查游戏内存偏移。
