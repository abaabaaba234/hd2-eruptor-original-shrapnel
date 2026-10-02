# 已验证的 ModOptionsMenu 接口

依据本机部署的 `mods/cowboybingus/mod_options_menu`：`api=1`、`version=2`。`version` 是菜单 API 能力版本，与 Bingus Shared Loader v18 无关。下面是该实现的观察结果，适配其他实现时重新检查。

已完成的适配实例：[hd2-eruptor-original-shrapnel v0.1.1](https://github.com/abaabaaba234/hd2-eruptor-original-shrapnel/tree/v0.1.1)。查阅 `src/core.lua` 的 `MENU_TEXT`、`menu_sync`、`menu_step`；测试见 `tests/test_runtime.py` 的 `menu_language_and_persistence`。

## 注册

```lua
local menu=rawget(_G,'ModOptionsMenu')
local ok,reason=menu.register_option('my_mod_count', {
    type='slider', mod=title, label=text('count'),
    min=1, max=64, step=1, default=config.count,
    description=text('count_description'),
})
```

`ok` 为 true 或 false，失败原因在第二返回值。`on_change` 也返回是否绑定成功。同一 ID 重复注册仅在规格等价时成功，不会借此替换已存的描述；重复 `on_change` 会累加回调。

- 注册顺序决定模组中的行顺序；用同一 `mod` 来源分组。
- `toggle.default` 必须是 boolean。Lua 中 0 也为真，不能把数字 0/1 直接当 toggle 值。
- `choice.choices` 为显示文本数组，值为 1-based 索引；原生 UI 的内部 0-based 行值不应出现在插件的 API 回调中。
- `slider` 会按步长对齐；插件仍应校验范围与业务规则。小数参数不能照搬整数校验。
- 当前实现支持 8 个模组按钮、每模组 32 个选项，choice 为 2–16 个文本。这些限制来自提供者，不要为了溢出控件修改别的模组。
- 文本长度按字符计算：mod 40、label 64、choice 48、description 400。控制字符、非法 UTF-8 会被拒绝。

## 应用与缓存

```lua
menu.on_change(id,function(value,option_id)
    -- value 已经应用；校验、更新配置、保存，再请求现有生效流程。
end)
local applied=menu.get(id)
local ok,reason=menu.set(id,wanted)
```

`get` 返回**已应用**值，用户暂存但尚未应用的改动不在其中。点击“应用”后，提供者按注册顺序调用变化项的回调，并保存自己的值缓存。

`set` 用代码改变已应用值，会撤销该项尚未应用的编辑、更新提供者缓存，并且**不会调用 on_change**。所以同步时仅在 get 与有效配置不相等时 set。相等时保留待应用的用户编辑。

注册时提供者缓存可覆盖 `default`。如果模组有独立配置，注册后进行一次差异同步，否则界面可能显示过去缓存的参数，与实际效果不一致。不要无条件把提供者旧缓存读回有效配置，也不要反复保存相同值。

## 动态文字与语言

`label`、`mod`、`description` 和每个 choice 文本可传函数。它们必须返回有效显示字符串：

```lua
local function text(key)
    return function() return translations[config.language][key] end
end
```

菜单打开时内部 `translation.refresh()` 会重新求值，更新模组的显示标题、参数标签及说明。分类内部 key 仍是初次注册的名称；切语言后无需新建分类或重注册。插件没有公开的 `menu.refresh()` 接口，不调用或猜测提供者私有函数。

mod 标题、choice 文本会自动变成大写，因此提供 `English` 会显示 `ENGLISH`。toggle 的原生 ON/OFF 字样由游戏自己翻译；本模组语言选项可翻译行标签与说明，但不能承诺原生 ON/OFF 或 MODS 总页也跟随此选项。

语言选择的示例是 `1 -> zh`、`2 -> en`。默认中文，旧配置无语言字段时补默认值并保留已有参数。不要翻译稳定 ID、配置键或语言代码。

## 与加载器的连接

v18 通过打包 Lua 开头的 `-- HD2-Addon: mods/author/resource` 声明发现模组。新增控件代码放在已有 addon 内，通常不需要改加载器、原生 UI 内存或资源哈希。若拆成新资源，则使用实际加载器支持的依赖方式，不凭空假设任意 Lua 文件可 require。

菜单全局变量可能较晚出现：在已有更新流程中低频重试绑定。成功后保持单个 adapter、单套回调；不支持的版本或注册失败记一次日志并停用菜单部分，让原有配置功能继续运行。适配模板对部分注册失败不会自动回滚，因当前 API 没有公开注销接口。

## 交付前有意义的检查

- UI 排序符合注册顺序，Language 是第一行，choice 索引映射正确。
- 同时应用语言和业务参数时两个值都保存，恢复运行后显示与效果一致。
- 菜单已有旧缓存时，有效配置优先；外部改配置后界面同步。
- 用户尚未应用的新值不会被相同配置的定时同步抹掉。
- 中文/英语切换后，只有模组文字与语言配置变化，业务参数和其他模组不变。
- 无菜单、旧版本菜单、注册失败时，核心配置机制继续运行；多次更新不会累加回调。
- 真实 UI 只能通过游戏内操作证明；离线注册/回调测试不能证明中文字体、排版或战斗行为。
