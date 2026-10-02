"""Exercise the shipped LuaJIT module against extracted native records."""
from pathlib import Path
import json, os, re, struct, sys, tempfile, zipfile
from unittest import SkipTest
from lupa import luajit21

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT/'src/core.lua').read_bytes()
BASE = 0x180000000
TABLES = {'projectile': 0x37c7670, 'explosion': 0x37cc920, 'damage': 0x37c60c0}
U = lambda n: struct.pack('<I', n)
Q = lambda n: struct.pack('<Q', n)
VANILLA = U(30)+U(201)
ORIGINAL = U(25)+U(228)
ANCHORS = {
    0x8525ba: '488bbcc170767c03',
    0x7b8483: '498b84c420c97c03f30f104014',
    0x1762dbb: '418b403cc745e00100000085c07505498bc4eb08488b84c1c0607c03',
}

class Memory:
    def __init__(self):
        self.pages = {}
        self.writes = []
        self.protects = []
        self.protection = 4
        self.failures = []
        self.fail_protect = None
        self.executable = False
        self.module_loaded = True

    def put(self, address, data):
        for i, value in enumerate(data):
            self.pages.setdefault((address+i)>>12, bytearray(4096))[(address+i)&4095] = value

    def read(self, address, n):
        result = bytearray()
        for i in range(n):
            page = self.pages.get((address+i)>>12)
            if page is None:
                return None
            result.append(page[(address+i)&4095])
        return bytes(result)

    def write(self, address, data):
        self.writes.append((address, data))
        if self.failures:
            length = self.failures.pop(0)
            self.put(address, data[:length])
            return False
        self.put(address, data)
        return True

    def query(self, address):
        protection = 0x20 if self.executable else self.protection
        return struct.pack('<QQIIQIIII', address & ~4095, address & ~4095,
                           protection, 0, 4096, 0x1000, protection, 0x20000, 0)

    def protect(self, address, n, value):
        self.protects.append(value)
        if self.fail_protect == value:
            self.fail_protect = None
            return 0
        self.protection = value
        return 1

class Scenario:
    def __init__(self, cfg=None, bad_build=False, bad_anchor=False, conflict=False):
        self.temp = tempfile.TemporaryDirectory(prefix='.run-', dir=ROOT/'tests')
        self.logs = Path(self.temp.name)/'CowboyBingus/Helldivers2/Logs'
        self.logs.mkdir(parents=True)
        if cfg is not None:
            (self.logs/'EruptorOriginalShrapnel.cfg').write_text(cfg)
        self.mem = Memory()
        self.addresses = {}
        self.initial = {}
        header = bytearray(4096)
        header[:2] = b'MZ'
        struct.pack_into('<I', header, 60, 0x100)
        header[0x100:0x104] = b'PE\0\0'
        struct.pack_into('<I', header, 0x108, 0 if bad_build else 0x6ab3b43f)
        struct.pack_into('<I', header, 0x150, 0x4744000)
        self.mem.put(BASE, header)
        for rva, code in ANCHORS.items():
            self.mem.put(BASE+rva, bytes.fromhex(code))
        if bad_anchor:
            self.mem.put(BASE+0x8525ba, b'\x90')
        fixture = json.loads((ROOT/'tests/fixtures/current_records.json').read_text())
        for index, (kind, records) in enumerate(fixture.items()):
            for record in records:
                t = record['type']
                address = 0x40000000+index*0x1000000+t*4096
                data = bytes.fromhex(record['hex'])
                self.mem.put(address, data)
                self.mem.put(BASE+TABLES[kind]+t*8, Q(address))
                self.addresses[(kind,t)] = address
                self.initial[(kind,t)] = data
        self.lua = luajit21.LuaRuntime(encoding=None)
        g = self.lua.globals()
        g[b'pyread'] = lambda p,n: self.mem.read(int(p),int(n))
        g[b'pywrite'] = lambda p,b: self.mem.write(int(p),bytes(b))
        g[b'pyquery'] = lambda p: self.mem.query(int(p))
        g[b'pyprotect'] = lambda p,n,v: self.mem.protect(int(p),int(n),int(v))
        g[b'pyprotection'] = lambda: self.mem.protection
        g[b'pymodule'] = lambda: BASE if self.mem.module_loaded else 0
        g[b'localpath'] = str(Path(self.temp.name)).encode()
        self.lua.execute(b'''
          local real=require('ffi');local ffi={};for k,v in pairs(real)do ffi[k]=v end
          ffi.cast=function(t,v)if type(v)=='function' then return v end;return real.cast(t,v)end
          local kernel={GetCurrentProcess=function()return real.cast('void *',1)end,
            GetModuleHandleA=function()return real.cast('void *',pymodule())end}
          kernel.ReadProcessMemory=function(_,p,b,n,count)
            local s=pyread(tonumber(real.cast('uintptr_t',p)),n)
            if not s then count[0]=0;return 0 end;real.copy(b,s,n);count[0]=n;return 1 end
          kernel.WriteProcessMemory=function(_,p,b,n,count)
            local ok=pywrite(tonumber(real.cast('uintptr_t',p)),real.string(b,n));count[0]=ok and n or 0;return ok and 1 or 0 end
          kernel.VirtualQuery=function(p,b,n)
            local s=pyquery(tonumber(real.cast('uintptr_t',p)));real.copy(b,s,n);return n end
          kernel.VirtualProtect=function(p,n,v,old)
            old[0]=pyprotection();return pyprotect(tonumber(real.cast('uintptr_t',p)),n,v)end
          ffi.load=function()return kernel end
          local old=require;require=function(name)if name=='ffi' then return ffi end;return old(name)end
          local getenv=os.getenv;os.getenv=function(k)if k=='LOCALAPPDATA' then return localpath end;return getenv(k)end
          print=function()end;calls=0;update=function(dt,extra)calls=calls+1;return dt,extra,42 end
        ''')
        if conflict:
            self.lua.execute(b'Hd2EruptorFragCone9={}')
        self.state = self.lua.eval(b'function(s)return assert(loadstring(s,"@core"))()end')(SOURCE)

    def tick(self, dt=1.1):
        return self.lua.eval(b'function(dt)return update(dt,"preserved")end')(dt)

    def cfg(self, text):
        (self.logs/'EruptorOriginalShrapnel.cfg').write_text(text)
        return self.tick()

    def raw(self, kind, t):
        return self.mem.read(self.addresses[(kind,t)], len(self.initial[(kind,t)]))

    def fields(self):
        return self.raw('explosion',158)[0x50:0x58]

    def close(self):
        self.lua = None
        self.temp.cleanup()

def defaults_and_restoration():
    s = Scenario()
    try:
        assert s.tick() == (1.1,b'preserved',42)
        assert s.state[b'phase'] == b'active' and s.fields() == ORIGINAL
        for key, original in s.initial.items():
            expected = original[:0x50]+ORIGINAL+original[0x58:] if key == ('explosion',158) else original
            assert s.raw(*key) == expected, key
        assert s.mem.writes == [(s.addresses[('explosion',158)]+0x50,ORIGINAL)]
        s.tick();assert len(s.mem.writes) == 1
        s.cfg('enabled=0\ncount=25\n')
        assert s.fields() == VANILLA and s.state[b'phase'] == b'disabled'
        s.cfg('enabled=1\ncount=25\n');assert s.fields() == ORIGINAL
    finally:
        s.close()

def count_changes():
    s = Scenario()
    try:
        s.tick()
        for n in [1,30,64,25]:
            s.cfg(f'enabled=1\ncount={n}\n');assert s.fields() == U(n)+U(228)
        s.cfg('enabled=0\ncount=25\n');assert s.fields() == VANILLA
    finally:s.close()

def invalid_config():
    s = Scenario()
    try:
        s.tick()
        for value in ['0','65','1.5','nan','nonsense']:
            before = len(s.mem.writes)
            s.cfg('enabled=1\ncount='+value+'\n')
            assert s.fields() == ORIGINAL and len(s.mem.writes) == before
        s.cfg('enabled=2\ncount=30\n');assert s.fields() == ORIGINAL
    finally:s.close()

def compatibility_guards():
    for options in [{'bad_build':True},{'bad_anchor':True},{'conflict':True}]:
        s = Scenario(**options)
        try:
            s.tick();assert s.state[b'phase'] == b'stopped' and not s.mem.writes
        finally:s.close()
    for kind,t,offset in [('damage',190,4),('projectile',228,0x3c),('projectile',40,0xf0),('explosion',158,0x10),('explosion',158,0x50)]:
        s = Scenario()
        try:
            s.mem.put(s.addresses[(kind,t)]+offset,U(999))
            s.tick();assert s.state[b'phase'] == b'stopped' and not s.mem.writes
        finally:s.close()

def wait_for_tables():
    s = Scenario()
    try:
        s.mem.module_loaded = False;s.tick();assert s.state[b'phase'] == b'waiting' and not s.mem.writes
        s.mem.module_loaded = True
        s.mem.put(BASE+TABLES['explosion']+158*8,Q(0))
        s.tick();assert s.state[b'phase'] == b'waiting' and not s.mem.writes
        s.mem.put(BASE+TABLES['explosion']+158*8,Q(s.addresses[('explosion',158)]))
        s.tick();assert s.fields() == ORIGINAL
    finally:s.close()

def record_movement():
    s = Scenario()
    try:
        s.tick();old = s.addresses[('explosion',158)];new = 0x52000000
        s.mem.put(new,s.initial[('explosion',158)])
        s.mem.put(BASE+TABLES['explosion']+158*8,Q(new));s.tick()
        assert s.mem.read(new+0x50,8) == ORIGINAL
        assert s.mem.read(old+0x50,8) == ORIGINAL
        s.cfg('enabled=0\ncount=25\n');assert s.mem.read(new+0x50,8) == VANILLA
        assert not any(p==old+0x50 for p,_ in s.mem.writes[1:])
    finally:s.close()

def temporary_dependency_loss():
    s = Scenario()
    try:
        s.tick()
        slot=BASE+TABLES['projectile']+228*8
        s.mem.put(slot,Q(0));s.tick()
        assert s.state[b'phase'] == b'waiting' and s.fields() == VANILLA
        s.mem.put(slot,Q(s.addresses[('projectile',228)]));s.tick()
        assert s.state[b'phase'] == b'active' and s.fields() == ORIGINAL
    finally:s.close()

def other_writer():
    s = Scenario()
    try:
        s.tick();alien = U(17)+U(201)
        s.mem.put(s.addresses[('explosion',158)]+0x50,alien)
        before = len(s.mem.writes);s.tick()
        assert s.state[b'phase'] == b'stopped' and s.fields() == alien
        assert len(s.mem.writes) == before
    finally:s.close()

def partial_write_rollback():
    for prefix in [0,1,4,5,7,8]:
        for fail_rollback in [False,True]:
            s = Scenario()
            try:
                s.mem.failures = [prefix]+([0] if fail_rollback else [])
                s.tick();assert s.state[b'phase'] == b'stopped' and s.fields() == VANILLA
            finally:s.close()

def restore_retry():
    s = Scenario()
    try:
        s.tick();s.mem.failures = [5]
        s.cfg('enabled=0\ncount=25\n');assert s.state[b'phase'] != b'disabled'
        s.tick();assert s.state[b'phase'] == b'disabled' and s.fields() == VANILLA
    finally:s.close()

def page_protection():
    s = Scenario()
    try:
        s.mem.protection = 2;s.tick()
        assert s.fields() == ORIGINAL and s.mem.protection == 2 and s.mem.protects == [4,2]
        s.cfg('enabled=0\ncount=25\n');assert s.fields() == VANILLA and s.mem.protection == 2
    finally:s.close()
    s = Scenario()
    try:
        s.mem.protection = 2;s.mem.fail_protect = 2;s.tick()
        assert s.fields() == ORIGINAL and s.mem.protection == 2
    finally:s.close()
    s = Scenario()
    try:
        s.mem.executable = True;s.tick()
        assert s.state[b'phase'] == b'stopped' and not s.mem.writes
    finally:s.close()
    s = Scenario()
    try:
        s.mem.protection = 2;s.mem.fail_protect = 4;s.tick()
        assert s.state[b'phase'] == b'stopped' and s.fields() == VANILLA and not s.mem.writes
    finally:s.close()

def optional_menu():
    s = Scenario()
    try:
        s.tick()
        s.lua.execute(b'''
          options={};changes={};values={};ModOptionsMenu={version=2,
            register_option=function(id,spec)options[id]=spec;values[id]=spec.default;return true end,
            on_change=function(id,fn)changes[id]=fn;return true end,
            get=function(id)return values[id]end,
            set=function(id,v)values[id]=v;return true end}
        ''')
        s.tick();options=s.lua.globals()[b'options'];changes=s.lua.globals()[b'changes']
        assert options[b'eruptor_original_count'][b'default'] == 25
        changes[b'eruptor_original_count'](30);s.tick();assert s.fields() == U(30)+U(228)
        changes[b'eruptor_original_enabled'](False);s.tick();assert s.fields() == VANILLA
        assert 'enabled=0' in (s.logs/'EruptorOriginalShrapnel.cfg').read_text()
    finally:s.close()

def load_real_menu(s):
    # Run the installed provider's real registration/persistence API and heap
    # descriptors, stopping before its native game-UI update hook is installed.
    path=Path(os.environ.get('HD2_MOD_OPTIONS_MENU_SOURCE',
        ROOT/'research/references/mod_options_menu_9ba626afa44a3aa3.patch_15.lua'))
    if not path.is_file():
        raise SkipTest('Set HD2_MOD_OPTIONS_MENU_SOURCE to the installed ModOptionsMenu Lua source')
    source=path.read_bytes()
    prefix=source.split(b'_G.ModOptionsMenu = api',1)[0]
    assert len(prefix)>50000
    return s.lua.execute(prefix+b'''\n_G.ModOptionsMenu=api
      return {api=api,state=state,translation=translation,
              set_pending=set_pending,apply_pending=apply_pending}''')

def menu_language_and_persistence():
    s=Scenario(cfg='enabled=1\ncount=31\n')
    try:
        menu=load_real_menu(s);s.tick()
        api=menu[b'api'];state=menu[b'state'];options=state[b'options']
        language=options[b'eruptor_original_language'];enabled=options[b'eruptor_original_enabled']
        count=options[b'eruptor_original_count'];mod=state[b'mods'][language[b'mod']]
        assert [mod[b'order'][i][b'id'] for i in (1,2,3)] == [
            b'eruptor_original_language',b'eruptor_original_enabled',b'eruptor_original_count']
        assert language[b'label'] == b'Language'
        assert language[b'choices'][1] == '简体汉字'.encode()
        assert language[b'choices'][2] == b'ENGLISH'
        assert enabled[b'label'] == '启用'.encode()
        assert api[b'get'](b'eruptor_original_count') == 31
        writes=len(s.mem.writes)
        menu[b'set_pending'](b'eruptor_original_language',2);s.tick()
        assert enabled[b'label'] == '启用'.encode()  # no change before Apply
        assert menu[b'apply_pending']() == 1
        s.tick();menu[b'translation'][b'refresh']()
        assert enabled[b'label'] == b'ENABLE' and mod[b'title'] == b'R-36 ORIGINAL SHRAPNEL'
        assert count[b'label'] == b'FRAGMENT COUNT (original 25)'
        assert language[b'label'] == b'Language'
        assert len(s.mem.writes) == writes and s.fields() == U(31)+U(228)
        saved=(s.logs/'EruptorOriginalShrapnel.cfg').read_text()
        assert 'language=en' in saved and 'count=31' in saved
        menu[b'set_pending'](b'eruptor_original_language',1)
        menu[b'set_pending'](b'eruptor_original_count',25)
        assert menu[b'apply_pending']() == 2
        s.tick();menu[b'translation'][b'refresh']()
        assert enabled[b'label'] == '启用'.encode() and s.fields() == ORIGINAL
        s.cfg('enabled=0\ncount=37\nlanguage=en\n')
        assert api[b'get'](b'eruptor_original_language') == 2
        assert api[b'get'](b'eruptor_original_count') == 37
        assert api[b'get'](b'eruptor_original_enabled') is False and s.fields() == VANILLA
    finally:s.close()
    s=Scenario(cfg=saved)
    try:
        # The mod's config wins over stale values in the provider's own cache.
        menu=load_real_menu(s)
        s.lua.globals()[b'test_menu_state']=menu[b'state']
        s.lua.execute(b'''test_menu_state.saved={eruptor_original_language='1',
          eruptor_original_count='10',eruptor_original_enabled='false'}''')
        s.tick()
        assert menu[b'api'][b'get'](b'eruptor_original_language') == 2
        assert menu[b'api'][b'get'](b'eruptor_original_count') == 31
        assert menu[b'api'][b'get'](b'eruptor_original_enabled') is True
        assert menu[b'state'][b'options'][b'eruptor_original_enabled'][b'label'] == b'ENABLE'
        s.cfg('enabled=0\ncount=12\nlanguage=invalid\n')
        assert s.fields() == U(31)+U(228) and menu[b'api'][b'get'](b'eruptor_original_language') == 2
    finally:s.close()

def optional_menu_failure():
    s = Scenario()
    try:
        s.lua.execute(b'ModOptionsMenu={version=2,register_option=function()error("unavailable")end,on_change=function()end}')
        s.tick();assert s.fields() == ORIGINAL and s.state[b'phase'] == b'active'
        s.cfg('enabled=0\ncount=25\n');assert s.fields() == VANILLA
    finally:s.close()

def singleton_and_callback():
    s = Scenario()
    try:
        s.tick()
        s.lua.eval(b'function(s)return assert(loadstring(s))()end')(SOURCE)
        before=s.lua.globals()[b'calls'];s.tick();assert s.lua.globals()[b'calls'] == before+1
        assert len(s.mem.writes) == 1
    finally:s.close()

def package_integrity():
    sys.path.insert(0,str(ROOT/'tools'))
    from build import build, murmur64, RESOURCE
    assert murmur64(b'mods/hd2mods/eruptor_frag_cone_v23') == 0x1bf248d50f0ed8c3
    output=build()
    with zipfile.ZipFile(output) as archive:
        manifest=json.loads(archive.read('manifest.json'))
        assert manifest['Version'] == 1 and manifest['Name'].endswith('v0.1.1')
        for description in [manifest['Description'],manifest['Options'][0]['Description']]:
            assert '不与破片向前' not in description and '尚待游戏实测' not in description
        assert manifest['Options'][0]['Include'] == ['Addon']
        data=archive.read('Addon/9ba626afa44a3aa3.patch_0')
        assert struct.unpack_from('<4I',data) == (0xf0000011,1,1,0)
        row=struct.unpack_from('<7Q6I',data,104)
        assert row[:3] == (murmur64(RESOURCE.encode()),0xa14e8dfa2cd117e2,192)
        size,encoding=struct.unpack_from('<II',data,192)
        assert encoding == 2 and data[200:200+size] == SOURCE.replace(b'\r\n',b'\n')
        assert row[7] == size+8 and struct.unpack_from('<Q',data,32)[0] == len(data)
        declaration=re.match(rb'^-- HD2-Addon: (mods/[A-Za-z0-9_]+/[A-Za-z0-9_/]+)',SOURCE)
        assert declaration and declaration[1].decode() == RESOURCE
        for suffix in ['.stream','.gpu_resources']:
            assert archive.read('Addon/9ba626afa44a3aa3.patch_0'+suffix) == b''

def historical_evidence():
    root=ROOT/'research/historical'
    explosions=json.loads((root/'explosion.json').read_text())[0]['ExplosionSettings']['items']
    projectiles=json.loads((root/'projectile.json').read_text())[0]['ProjectileSettings']['items']
    damage=json.loads((root/'damage.json').read_text())[1]['DamageSettings']['items']
    for kind in ['ExplosionType_Flak_20mm','ExplosionType_JarPhoenix_20mm']:
        record=next(x for x in explosions if x['type']==kind)
        assert record['num_shrapnel_projectiles'] == 25
        assert record['shrapnel_projectile_type'] == 'ProjectileType_Shrapnel_High_Velocity'
    projectile=next(x for x in projectiles if x['type']=='ProjectileType_Shrapnel_High_Velocity')
    assert projectile['speed'] == 1000 and projectile['life_time'] == 2
    record=next(x for x in damage if x['type']==projectile['damage_info_type'])
    assert record['damage'] == [300,150] and record['armor_penetration_per_angle'] == [3,3,3,0]

TESTS=[defaults_and_restoration,count_changes,invalid_config,compatibility_guards,
       wait_for_tables,record_movement,temporary_dependency_loss,other_writer,partial_write_rollback,restore_retry,
       page_protection,optional_menu,menu_language_and_persistence,optional_menu_failure,
       singleton_and_callback,package_integrity,historical_evidence]
if __name__ == '__main__':
    passed=[];skipped=[]
    for test in TESTS:
        try:
            test();passed.append(test.__name__);print('PASS',test.__name__)
        except SkipTest as reason:
            skipped.append(test.__name__);print('SKIP',test.__name__,str(reason))
    output=ROOT/'validation/report.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({'version':'0.1.1','game_build':25480438,'tests_passed':passed,'tests_skipped':skipped,
        'lua_runtime':'LuaJIT2.1 through lupa','mutation':'ExplosionInfo158 +0x50..0x57:30/201 to25/228',
        'original_count':25,'damage':[300,150],'armor_penetration':[3,3,3,0],
        'live_startup_verified':False,'battlefield_verified':False,'multiplayer_verified':False},indent=2))
    print('Passed',len(passed),'test groups')
