# Evidence and implementation scope

## Original configuration

The April 16, 2024 data snapshot is pinned to shalzuth/HelldiversData commit `9e1452b55f9c086e8aabeeb5acc43ebcd76f85ba`. Both the original `Flak_20mm` explosion and the `JarPhoenix_20mm` Eruptor variant name **25** `ProjectileType_Shrapnel_High_Velocity` projectiles. The high-velocity projectile uses `DamageInfoType_Projectile_Shrapnel_High_Velocity`: **300/150** damage and **3/3/3/0** armor penetration.

- [Historical explosion records](https://github.com/shalzuth/HelldiversData/blob/9e1452b55f9c086e8aabeeb5acc43ebcd76f85ba/data/settings/generated_explosion_settings.json)
- [Historical projectile records](https://github.com/shalzuth/HelldiversData/blob/9e1452b55f9c086e8aabeeb5acc43ebcd76f85ba/data/settings/generated_projectile_settings.json)
- [Historical damage records](https://github.com/shalzuth/HelldiversData/blob/9e1452b55f9c086e8aabeeb5acc43ebcd76f85ba/data/settings/generated_damage_settings.json)
- [Eruptor Wiki and change history](https://helldivers.wiki.gg/wiki/R-36_Eruptor)
- [Orbital Airburst Wiki: shared 300/150 damage profile](https://helldivers.wiki.gg/wiki/Orbital_Airburst_Strike)

The Wiki records 30 current fragments and the September 17, 2024 replacement with frag-grenade shrapnel. The historical snapshot supplies the exact original count that the current Wiki does not preserve in its detailed table. Old high-velocity fragments and current heavy orbital fragments share damage, but current heavy fragments include an impact explosion; borrowing the heavy projectile would add behavior absent from the old Eruptor projectile.

## Current layout

filediver commit `7b52b323b1cd75326f63c5854c3a38b60a547e32` supplies extracted projectile, explosion and damage tables; local downloaded research copies are pinned. Relevant records:

| Record | ID | Role |
| --- | --- | --- |
| ProjectileInfo | 40 | Current Eruptor main projectile |
| ExplosionInfo | 158 | Current Eruptor impact and expiry explosion |
| ProjectileInfo | 201 | Current shared frag projectile, 110/35 damage |
| ProjectileInfo | 228 | Original high-velocity projectile, 1000 m/s, 2 s lifetime |
| DamageInfo | 190 | Original 300/150, AP 3/3/3/0 damage profile |

[filediver](https://github.com/xypwn/filediver/tree/7b52b323b1cd75326f63c5854c3a38b60a547e32/datalibrary) has stale Go fields around projectile lifetime: the current installed type library and native instructions place lifetime at +0x34, lifetime randomness at +0x38 and damage-info type at +0x3c. The addon does not use the old parser's +0x38 damage offset. ProjectileInfo is 272 bytes, ExplosionInfo is 152 bytes and DamageInfo is 76 bytes.

The installed Steam manifest confirms build25480438. Offline native code previously captured for this build supplies lookup signatures, rechecked here, and the plugin validates all of them in-process before writing:

| Lookup | game.dll RVA | Proof instruction RVA |
| --- | --- | --- |
| ProjectileInfo pointer array | 0x37c7670 | 0x8525ba |
| ExplosionInfo pointer array | 0x37cc920 | 0x7b8483 |
| DamageInfo pointer array | 0x37c60c0 | 0x1762dcf; field read at0x1762dbb |

PE timestamp must equal 0x6ab3b43f and SizeOfImage must equal 0x4744000. Pointer lookup avoids whole-process scans. No executable instructions are modified.

## Mutation and restoration

The only target is ExplosionInfo158 +0x50..0x57: two contiguous uint32 values change from `30,201` to `25,228`. The addon checks shell identity, explosion radii/damage identity, high-velocity ballistics/flags, and the complete DamageInfo190 record before changing these fields. All projectile and damage records remain untouched, including definitions shared with autocannon, hand grenades and orbital weapons. The current explosion's other fields remain unchanged.

The plugin saves originals, verifies each write, rejects another writer's values, and avoids stale record addresses. Failed prefix writes are rolled back with matching-byte checks. Read-only private data pages are temporarily made writable and restored; executable pages are rejected. Unknown game versions stop before writing.

The supplied Forward Fragments v2.3 archive was extracted read-only for comparison of structures and optional menu APIs. It is incompatible when simultaneously enabled because it would tune the borrowed high-velocity projectile shared by other weapons. No source from that mod or from filediver is distributed in the runtime module.

## Verification status

v0.1.1 registers Language first, followed by enable and count. The deployed ModOptionsMenu exposes API1/version2: `choice` values are 1-based; registration order controls row order; labels, descriptions and category titles accept functions refreshed when the Esc menu opens. This addon uses those functions to resolve its own Chinese/English texts without changing the menu provider or other mods. Choice captions use the provider's uppercase styling. Configuration remains authoritative over menu-provider cached values. The package's public description ends at quantity/language controls, with the requested trailing text removed.

The shipped source runs in LuaJIT against current extracted records with sanitized pointers. The package checker validates resource hash, archive entries, source declaration and zipped/source equality. These checks prove offline structure and field behavior; they do not prove game startup, enemy damage, ricochets, spawn physics or multiplayer synchronization. No live-process access or live deployment was performed for this request.
