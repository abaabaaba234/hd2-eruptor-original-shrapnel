"""Build a discovered Lua addon archive for Bingus Shared Loader v18."""
from pathlib import Path
import hashlib, json, struct, zipfile

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = 'mods/eruptor_original_shrapnel/core'
VERSION = '0.1.1'

def murmur64(data):
    mask = (1 << 64) - 1
    mix = 0xc6a4a7935bd1e995
    h = len(data) * mix & mask
    for i in range(0, len(data) // 8 * 8, 8):
        k = int.from_bytes(data[i:i+8], 'little') * mix & mask
        k ^= k >> 47
        k = k * mix & mask
        h = (h ^ k) * mix & mask
    tail = data[len(data)//8*8:]
    if tail:
        h = (h ^ int.from_bytes(tail, 'little')) * mix & mask
    h ^= h >> 47
    h = h * mix & mask
    return h ^ (h >> 47)

def patch(source):
    body = struct.pack('<II', len(source), 2) + source
    offset = 192
    size = max(4096, (offset + len(body) + 15) & ~15)
    kind = 0xa14e8dfa2cd117e2
    header = struct.pack('<4I', 0xf0000011, 1, 1, 0) + bytes(16) + struct.pack('<Q', size) + bytes(32)
    type_entry = struct.pack('<IIQQII', 0, 0, kind, 1, 16, 16)
    entry = struct.pack('<7Q6I', murmur64(RESOURCE.encode()), kind, offset, 0, 0, 0, 0, len(body), 0, 0, 16, 16, 0)
    return header + type_entry + entry + bytes(offset-len(header+type_entry+entry)) + body + bytes(size-offset-len(body))

def build():
    description = ('恢复初版爆裂铳25片高速破片，每片300普通/150耐久伤害，穿甲3/3/3/0。'
                   '仅替换爆裂铳的破片类型和数量。需要Bingus Shared Loader v18；'
                   '支持Steam build25480438。可选MODS菜单调节数量及语言。')
    manifest = {'Version': 1, 'Guid': '0483cadc-96a1-4ad1-8752-3cfc887d6833',
                'Name': '爆裂铳初版破片 / Eruptor Original Shrapnel v'+VERSION,
                'Description': description, 'Options': [{'Name': '初版25片高速破片 / Original25',
                    'Description': description, 'Include': ['Addon']}]}
    files = {'manifest.json': json.dumps(manifest, ensure_ascii=True, indent=2).encode('ascii')}
    source = (ROOT/'src/core.lua').read_bytes().replace(b'\r\n', b'\n')
    files['Addon/9ba626afa44a3aa3.patch_0'] = patch(source)
    files['Addon/9ba626afa44a3aa3.patch_0.stream'] = b''
    files['Addon/9ba626afa44a3aa3.patch_0.gpu_resources'] = b''
    for name in ['README_中文.md', 'RESEARCH.md', 'CREDITS.md']:
        files[name] = (ROOT/name).read_bytes()
    if (ROOT/'validation/report.json').exists():
        files['VALIDATION.json'] = (ROOT/'validation/report.json').read_bytes()
    output = ROOT/'dist'/('EruptorOriginalShrapnel_v'+VERSION+'.zip')
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 2, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    (ROOT/'manifest.json').write_bytes(files['manifest.json'])
    print(output)
    print('SHA256', hashlib.sha256(output.read_bytes()).hexdigest())
    return output

if __name__ == '__main__':
    build()
