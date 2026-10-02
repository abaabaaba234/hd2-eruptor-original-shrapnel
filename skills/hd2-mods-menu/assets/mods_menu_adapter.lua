-- Inline this file into the existing addon before constructing its adapter.
-- Example fields: enabled=0/1, count=number, language='zh'/'en'.
-- The host loads and validates config, owns persistence and applies effects.
local function create_mods_menu_adapter(spec)
    assert(type(spec.get_config)=='function' and type(spec.save_config)=='function',
        'Provide get_config and save_config')
    assert(type(spec.namespace)=='string' and spec.namespace:match('^[%w_]+$'),
        'Use a unique, stable option namespace')
    local range=assert(spec.count, 'Provide the parameter range')
    assert(type(range.min)=='number' and type(range.max)=='number' and range.min<range.max,
        'Invalid count range')
    local step=range.step or 1
    assert(type(step)=='number' and step>0 and step<=range.max-range.min, 'Invalid step')
    local titles=spec.titles or {zh='我的模组',en='MY MOD'}
    local ids={language=spec.namespace..'_language',enabled=spec.namespace..'_enabled',
        count=spec.namespace..'_count'}
    local texts={
        zh={enabled='启用',count='数量',
            language_description='选择本模组语言。应用后关闭并重新打开 Esc 菜单刷新文字。',
            enabled_description='开启或关闭本模组效果。',
            count_description='调整数量；应用后保存并生效。'},
        en={enabled='ENABLE',count='COUNT',
            language_description='Select this mod\'s language. Apply, then close and reopen the Esc menu.',
            enabled_description='Enable or disable this mod.',
            count_description='Adjust the count. Apply to save and use the value.'},
    }
    local api,blocked
    local function language()
        return spec.get_config().language=='en' and 'en' or 'zh'
    end
    local function text(key)
        return function()return texts[language()][key]end
    end
    local function title()return titles[language()]end
    local function persist(effect_changed)
        spec.save_config()
        if effect_changed and type(spec.request_apply)=='function' then spec.request_apply()end
    end
    local function checked(ok,reason)
        if ok~=true then error(tostring(reason or 'Menu operation failed'),0)end
    end
    local function sync()
        local config=spec.get_config()
        local wanted={language=language()=='zh' and 1 or 2,
            enabled=config.enabled==1,count=config.count}
        for key,value in pairs(wanted)do
            if api.get(ids[key])~=value then checked(api.set(ids[key],value))end
        end
    end
    local function attach(menu)
        if (tonumber(menu.version) or 1)<2 then error('Requires ModOptionsMenu version2',0)end
        for _,method in ipairs{'register_option','on_change','get','set'}do
            if type(menu[method])~='function' then error('Missing menu API '..method,0)end
        end
        local config=spec.get_config()
        -- Registration order is the displayed row order.
        checked(menu.register_option(ids.language,{type='choice',mod=title,label='Language',
            choices={'简体汉字','English'},default=language()=='zh' and 1 or 2,
            description=text('language_description')}))
        checked(menu.register_option(ids.enabled,{type='toggle',mod=title,
            label=text('enabled'),default=config.enabled==1,description=text('enabled_description')}))
        checked(menu.register_option(ids.count,{type='slider',mod=title,
            label=text('count'),min=range.min,max=range.max,step=step,default=config.count,
            description=text('count_description')}))
        checked(menu.on_change(ids.language,function(value)
            if value~=1 and value~=2 then return end
            spec.get_config().language=value==1 and 'zh' or 'en'
            persist(false)
        end))
        checked(menu.on_change(ids.enabled,function(value)
            if type(value)~='boolean' then return end
            spec.get_config().enabled=value and 1 or 0
            persist(true)
        end))
        checked(menu.on_change(ids.count,function(value)
            if type(value)~='number' or value~=value or value<range.min or value>range.max then return end
            local n=(value-range.min)/step
            if math.abs(n-math.floor(n+0.5))>1e-6 then return end
            spec.get_config().count=value
            persist(true)
        end))
        api=menu
        sync() -- The host config wins over the provider's stale cache.
    end
    local adapter={}
    function adapter.step()
        if blocked then return false,blocked end
        local ok,reason=pcall(function()
            if api then sync();return end
            local menu=rawget(_G,'ModOptionsMenu')
            if type(menu)~='table' then return end -- Retry after late loading.
            attach(menu)
        end)
        if not ok then
            blocked=tostring(reason)
            if type(spec.log)=='function' then spec.log('Optional MODS menu unavailable: '..blocked)end
            return false,blocked
        end
        return api~=nil
    end
    return adapter
end
