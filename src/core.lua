-- HD2-Addon: mods/eruptor_original_shrapnel/core
-- Restore the Eruptor's original 25 high-velocity fragments through loader v18.
local existing=rawget(_G,'EruptorOriginalShrapnel')
if existing then return existing end
local S={version='0.1.1',phase='waiting',writes=0,elapsed=0}
rawset(_G,'EruptorOriginalShrapnel',S)
local ffi=require('ffi')
local ROOT=(os.getenv('LOCALAPPDATA') or '')..'\\CowboyBingus\\Helldivers2\\Logs\\'
local CFG=ROOT..'EruptorOriginalShrapnel.cfg'
local LOG=ROOT..'EruptorOriginalShrapnel.log'
local first=true
local function log(message)
    S.status=message
    pcall(print,'[EruptorOriginalShrapnel] '..message)
    local f=io.open(LOG,first and 'w' or 'a')
    if f then first=false;f:write(os.date('%H:%M:%S ')..message..'\n');f:close() end
end
local config={enabled=1,count=25,language='zh'};S.config=config
local text_seen
local function read_config()
    local f=io.open(CFG,'rb')
    if not f then
        f=io.open(CFG,'wb')
        if f then f:write('# Original Eruptor: 25 fragments, 300/150 damage, AP 3/3/3/0.\n',
            '# Save to reload. count=1..64; 25 restores the original count.\n',
            '# language=zh (simplified Chinese) or en (English).\n',
            'enabled=1\ncount=25\nlanguage=zh\n');f:close();f=io.open(CFG,'rb') end
    end
    local text=f and f:read('*a') or '';if f then f:close() end
    if text==text_seen then return end
    text_seen=text
    local next_config={enabled=1,count=25,language='zh'}
    for line in text:gmatch('[^\r\n]+') do
        local key,value=line:match('^%s*([%w_]+)%s*=%s*([^%s#]+)')
        if key=='language' then
            if value~='zh' and value~='en' then log('Config rejected: language='..tostring(value));return end
            next_config.language=value
        elseif next_config[key]~=nil then
            local n=tonumber(value)
            if not n or n%1~=0 or (key=='enabled' and n~=0 and n~=1)
                or (key=='count' and (n<1 or n>64)) then
                log('Config rejected: '..key..'='..tostring(value));return
            end
            next_config[key]=n
        end
    end
    for k,v in pairs(next_config) do config[k]=v end
end
local function save_config()
    local f=io.open(CFG,'wb');if not f then return false end
    f:write('# Original Eruptor count is25. Save to reload.\n',
        'enabled='..config.enabled..'\ncount='..config.count..'\nlanguage='..config.language..'\n');f:close()
    text_seen=nil;return true
end
local K={}
local lib=ffi.load('kernel32')
for _,d in ipairs({
    {'GetCurrentProcess','void *','(void)'},
    {'GetModuleHandleA','void *','(const char *)'},
    {'ReadProcessMemory','int','(void *, const void *, void *, size_t, size_t *)'},
    {'WriteProcessMemory','int','(void *, void *, const void *, size_t, size_t *)'},
    {'VirtualQuery','size_t','(const void *, void *, size_t)'},
    {'VirtualProtect','int','(void *, size_t, uint32_t, uint32_t *)'},
}) do
    pcall(ffi.cdef,d[2]..' '..d[1]..d[3]..';')
    local ok,fn=pcall(function()return ffi.cast(d[2]..' (*)'..d[3],lib[d[1]])end)
    if not ok then S.phase='stopped';log('Cannot bind '..d[1]);return S end
    K[d[1]]=fn
end
local process=K.GetCurrentProcess()
local buffer=ffi.new('uint8_t[512]');local got=ffi.new('size_t[1]')
local mbi=ffi.new('uint8_t[48]')
local function read(p,n)
    if type(p)~='number' or p<0x10000 or p+n>0x7fffffff0000 or n<1 or n>512 then return nil end
    got[0]=0
    if K.ReadProcessMemory(process,ffi.cast('const void *',p),buffer,n,got)==0 or tonumber(got[0])~=n then return nil end
    return ffi.string(buffer,n)
end
local function u32(s,o)
    local a,b,c,d=s:byte(o+1,o+4)
    return a and d and a+b*256+c*65536+d*16777216 or nil
end
local function u64(s,o)return u32(s,o)+u32(s,o+4)*4294967296 end
local function pointer(p)local b=read(p,8);return b and u64(b,0) or nil end
local function word(n)return ffi.string(ffi.new('uint32_t[1]',n),4)end
local function unhex(s)return(s:gsub('..',function(x)return string.char(tonumber(x,16))end))end
local function write(p,b)
    if K.VirtualQuery(ffi.cast('const void *',p),mbi,48)~=48 then return false end
    local q=ffi.string(mbi,48);local protect=u32(q,36)
    if u32(q,32)~=0x1000 or u32(q,40)~=0x20000 or (protect~=2 and protect~=4)
        or p+#b>u64(q,0)+u64(q,24) then return false end
    local old=ffi.new('uint32_t[1]')
    if protect==2 and K.VirtualProtect(ffi.cast('void *',p),#b,4,old)==0 then return false end
    local ok=K.WriteProcessMemory(process,ffi.cast('void *',p),b,#b,got)~=0
        and tonumber(got[0])==#b and read(p,#b)==b
    if protect==2 and K.VirtualProtect(ffi.cast('void *',p),#b,protect,old)==0 then
        -- Retry a transient protection restore failure before any rollback.
        if K.VirtualProtect(ffi.cast('void *',p),#b,protect,old)==0 then return false end
    end
    if ok then S.writes=S.writes+1 end
    return ok
end
local ANCHORS={
    {0x8525ba,'488bbcc170767c03'}, -- ProjectileInfo pointer array.
    {0x7b8483,'498b84c420c97c03f30f104014'}, -- ExplosionInfo pointer array.
    {0x1762dbb,'418b403cc745e00100000085c07505498bc4eb08488b84c1c0607c03'}, -- DamageInfo at ProjectileInfo +0x3c.
}
local function check_build()
    local base=tonumber(ffi.cast('uintptr_t',K.GetModuleHandleA('game.dll')))
    if not base or base==0 then return nil end
    local dos=read(base,64)
    if not dos or dos:sub(1,2)~='MZ' then error('Invalid game module') end
    local pe=read(base+u32(dos,60),96)
    if not pe or pe:sub(1,4)~='PE\0\0' or u32(pe,8)~=0x6ab3b43f or u32(pe,80)~=0x4744000 then
        error('Unsupported build; expected Steam25480438 / EXE1.8.46015.0')
    end
    for _,a in ipairs(ANCHORS) do
        local b=unhex(a[2]);if read(base+a[1],#b)~=b then error('Native lookup signature differs') end
    end
    return base
end
-- Stable bytes from filediver's extracted current tables, checked against the
-- installed type library. Its Go parser has an obsolete lifetime layout; the
-- real damage-info field is +0x3c, lifetime +0x34, randomness +0x38.
local SHELL_HEAD=unhex('28000000886c5d0969f200886952cdf1f5c84b7d5898656a0000704101000000000034430000c842000000009a99993e010000000000803f00000000950000000000803e')
local FRAGMENT_HEAD=unhex('e400000088224b8424ad4a846952cdf1f5c84b7d5898656a000080400100000000007a4400000040cdcccc3e0000803f010000000000004000000000be0000000000803e')
local DAMAGE=unhex('be0000002c01000096000000030000000300000003000000000000000a0000000a00000014000000000000000000000000000000000000000000000000000000000000000000000000000000')
local EXPLOSION_HEAD=unhex('9e0000005b0100000000000000000000000080400000e04000000041000000000000204200000000')
local VANILLA=word(30)..word(201)
local function get_record(table_rva,t,n)
    local p=pointer(S.base+table_rva+t*8)
    if not p or p==0 then return nil end
    local b=read(p,n);if not b then return nil end
    if u32(b,0)~=t then error('Native record identity differs: '..t) end
    return {addr=p,bytes=b,table_rva=table_rva,type=t}
end
local function records()
    local shell=get_record(0x37c7670,40,272)
    local explosion=get_record(0x37cc920,158,152)
    local fragment=get_record(0x37c7670,228,272)
    local damage=get_record(0x37c60c0,190,76)
    if not shell or not explosion or not fragment or not damage then return nil end
    if shell.bytes:sub(1,#SHELL_HEAD)~=SHELL_HEAD or u32(shell.bytes,0x90)~=158
        or u32(shell.bytes,0x9c)~=158 or u32(shell.bytes,0xf0)~=0x19 then error('Eruptor shell modified') end
    if explosion.bytes:sub(1,#EXPLOSION_HEAD)~=EXPLOSION_HEAD then error('Eruptor explosion modified') end
    if fragment.bytes:sub(1,#FRAGMENT_HEAD)~=FRAGMENT_HEAD or u32(fragment.bytes,0x90)~=0
        or u32(fragment.bytes,0x9c)~=0 or u32(fragment.bytes,0xf0)~=0x3d then error('High-velocity shrapnel modified') end
    if damage.bytes~=DAMAGE then error('Original300/150 AP3 damage profile modified') end
    return explosion
end
local function same_record(r)
    return pointer(S.base+r.table_rva+r.type*8)==r.addr
        and read(r.addr,#EXPLOSION_HEAD)==EXPLOSION_HEAD
end
local function restore()
    local r=S.owned;if not r then return true end
    if not same_record(r) then
        S.owned=nil;log('Record moved; abandoned stale ownership');return true
    end
    local current=read(r.addr+0x50,8)
    if current==r.original then S.owned=nil;return true end
    if current~=r.last then
        S.owned=nil;log('Restore skipped: another writer changed shrapnel fields');return false
    end
    if not write(r.addr+0x50,r.original) then
        local after=read(r.addr+0x50,8)
        if after then
            for n=0,8 do
                if after==r.original:sub(1,n)..current:sub(n+1) then r.last=after;break end
            end
        end
        log('Restore failed; will retry');return false
    end
    S.owned=nil;log('Restored30 vanilla fragments');return true
end
local function stop(message)
    S.phase='stopped';restore();log(message)
end
local function apply(r)
    local owned=S.owned
    if owned and owned.addr~=r.addr then
        S.owned=nil;owned=nil;log('Record generation changed; stale row will not be touched')
    end
    local current=read(r.addr+0x50,8)
    if not owned then
        if current~=VANILLA then error('Shrapnel fields already modified; refusing conflict') end
        owned={addr=r.addr,type=r.type,table_rva=r.table_rva,original=current,last=current}
        S.owned=owned
    elseif current~=owned.last then
        error('Shrapnel fields changed by another writer')
    end
    local desired=word(config.count)..word(228)
    if current==desired then S.phase='active';return end
    if not same_record(r) then error('Record moved before write') end
    if not write(r.addr+0x50,desired) then
        -- A failed WriteProcessMemory may have written a prefix. Roll that
        -- prefix back only while the pointer and untouched suffix still match.
        local after=read(r.addr+0x50,8);local ours=false
        if after then
            for n=0,8 do
                if after==desired:sub(1,n)..current:sub(n+1) then ours=true;break end
            end
        end
        if ours and after~=current and same_record(r) then
            write(r.addr+0x50,current)
            -- Track a failed rollback too, so stop() can retry restoration.
            local recovery=read(r.addr+0x50,8)
            if recovery then
                for n=0,8 do
                    if recovery==current:sub(1,n)..after:sub(n+1) then owned.last=recovery;break end
                end
            end
        end
        error('Shrapnel write failed')
    end
    owned.last=desired;S.phase='active'
    log('Active: '..config.count..' high-velocity fragments;300/150 damage;AP3/3/3/0;1000m/s;2s lifetime')
end
local menu_registered=false
local menu_api
local MENU_IDS={language='eruptor_original_language',enabled='eruptor_original_enabled',count='eruptor_original_count'}
local MENU_TEXT={
    zh={title='R-36 爆裂铳初版破片',enabled='启用',count='破片数量（初版 25）',
        language_description='选择本模组的显示语言。应用后关闭并重新打开 Esc 菜单，文字随之更新。',
        enabled_description='启用初版高速破片。关闭后恢复当前原版的破片类型和数量。',
        count_description='初版为 25 片，当前原版为 30 片。每片伤害为 300 普通 / 150 耐久，穿甲为 3/3/3/0。'},
    en={title='R-36 ORIGINAL SHRAPNEL',enabled='ENABLE',count='FRAGMENT COUNT (original 25)',
        language_description='Select this mod\'s display language. Apply, then close and reopen the Esc menu to refresh the text.',
        enabled_description='Enable original high-velocity shrapnel. Off restores vanilla fragment type and count.',
        count_description='Original release: 25 fragments. Current vanilla: 30. Each fragment: 300/150 damage, AP 3/3/3/0.'},
}
local function menu_text(key)
    return function()return MENU_TEXT[config.language][key]end
end
local function menu_sync()
    if not menu_api or type(menu_api.get)~='function' or type(menu_api.set)~='function' then return end
    local wanted={language=config.language=='zh' and 1 or 2,enabled=config.enabled==1,count=config.count}
    for key,value in pairs(wanted) do
        local id=MENU_IDS[key]
        if menu_api.get(id)~=value then
            local ok,why=menu_api.set(id,value)
            if ok==false then error('Cannot synchronize menu option '..id..': '..tostring(why)) end
        end
    end
end
local function menu_step()
    if menu_registered then menu_sync();return end
    local menu=rawget(_G,'ModOptionsMenu')
    if type(menu)~='table' or type(menu.register_option)~='function' or type(menu.on_change)~='function' then return end
    if (tonumber(menu.version) or 1)<2 then error('Language controls require ModOptionsMenu version2') end
    local title=menu_text('title')
    local function register(id,spec)
        local ok,why=menu.register_option(id,spec)
        if ok==false then error('Cannot register '..id..': '..tostring(why)) end
    end
    -- Registration order is display order in ModOptionsMenu.
    register(MENU_IDS.language,{type='choice',mod=title,label='Language',
        choices={'简体汉字','English'},default=config.language=='zh' and 1 or 2,
        description=menu_text('language_description')})
    register(MENU_IDS.enabled,{type='toggle',mod=title,
        label=menu_text('enabled'),default=config.enabled==1,description=menu_text('enabled_description')})
    register(MENU_IDS.count,{type='slider',mod=title,
        label=menu_text('count'),min=1,max=64,step=1,default=config.count,
        description=menu_text('count_description')})
    menu.on_change(MENU_IDS.language,function(v)
        if v~=1 and v~=2 then return end
        config.language=v==1 and 'zh' or 'en';save_config();S.elapsed=1
    end)
    menu.on_change(MENU_IDS.enabled,function(v)config.enabled=v and 1 or 0;save_config();S.elapsed=1 end)
    menu.on_change(MENU_IDS.count,function(v)
        v=tonumber(v);if v and v%1==0 and v>=1 and v<=64 then config.count=v;save_config();S.elapsed=1 end
    end)
    menu_api=menu;menu_registered=true;menu_sync();log('Registered bilingual MODS menu;language='..config.language)
end
local function tick(dt)
    if S.phase=='stopped' then restore();return end
    S.elapsed=S.elapsed+(tonumber(dt) or 0)
    if S.elapsed<1 then return end;S.elapsed=0
    read_config()
    local menu_ok,menu_err=pcall(menu_step)
    if not menu_ok then menu_registered=true;log('Optional menu unavailable: '..tostring(menu_err)) end
    if not S.base then S.base=check_build();if not S.base then return end end
    if rawget(_G,'Hd2EruptorFragCone9') then error('Disable Forward Fragments v2.3 before using this addon') end
    if config.enabled~=1 then
        if restore() then S.phase='disabled' end
        return
    end
    local r=records()
    if not r then
        if S.owned then restore() end
        S.phase='waiting';return
    end
    apply(r)
end
read_config();log('Loaded v'..S.version..';original count25;waiting for native tables')
local function guarded(dt)
    local ok,err=pcall(tick,dt)
    if not ok then stop(tostring(err)) end
end
local previous_update=rawget(_G,'update')
if type(previous_update)=='function' then
    function update(...)
        guarded(select(1,...))
        return previous_update(...)
    end
else
    function update(...)guarded(select(1,...))end
end
return S
