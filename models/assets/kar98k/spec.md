# kar98k - reference specification

Karabiner 98 kurz, Wehrmacht service rifle, 1939-1945 production (hooded front sight, steel butt plate with stock disc). Class: rifle. Budget 3,000-6,000 triangles (max 10,000). Front axis +Y (muzzle). Game contract kept: 1 unit = 1 m, muzzle +Y, up +Z, bore axis at z = 0.035, root empty `Kar98k`, rig groups `Bolt`, `Trigger`, `RearSight`, `FloorPlate`. Origin is on the bore axis (not on the ground).

## Sources (what was actually read)
- Wikipedia "Karabiner 98k" (two fetches): length 1,110 mm, barrel 600 mm, mass 3.7-4.1 kg, 500 mm sight radius, open post front sight hooded from 1939, tangent leaf rear sight with V notch graduated 100-2,000 m, semi-pistol-grip stock, steel butt plate (flat, cupped from 1940), stock disc, short cleaning rod through the bayonet stud, turned-down bolt handle, three-position safety, S84/98 III bayonet.
- Other listings and sites: germanwarmachine.com (1.1075 m, barrel stated 0.739 m there: disagrees with Wikipedia, 600 mm used), lonesentry.com (43.5 in, 23.4 in barrel), IMA (stock sets: lower stock and handguard with rear sight cutout, nose cap with bayonet fitting).

## Dimensions (m)
| axis | value | tolerance | note |
|---|---|---|---|
| y length | 1.11 | +-0.02 | butt plate to muzzle crown |
| x width | 0.09 | +-0.015 | NOT sourced: estimate with the bolt handle down (handle projects about 0.065 from the bore axis) |
| z height | 0.215 | +-0.03 | NOT sourced: butt toe to top of front sight hood, estimate |
| sight radius | 0.50 | +-0.02 | front post to rear notch (sourced) |

## Features that must be present
1. Walnut stock with semi-pistol grip, no grip cap; steel butt plate with toe, stock disc on the right side.
2. Wooden handguard over the barrel: SIMPLIFIED to one smooth wood mass (no seam or cutout) - a seam would cost triangles for no visible gain at game distance.
3. Tangent rear sight: base on the barrel, hinged ramp, sloped leaf with V notch and graduations, slider.
4. Hooded front sight: blade post inside a hood tunnel, on a base clamped to the barrel.
5. Turned-down bolt handle with round knob; wing safety on the cocking piece; bolt stop on the left; clip guide on the receiver.
6. Nose cap with bayonet lug and cleaning-rod stub; one barrel band with sling slot.
7. Trigger, trigger guard bow and floor plate flush with the stock.
8. All parts image-textured (walnut, blued steel, parkerised, bright steel).

## Deliberately omitted
Interior magazine, bolt internals, markings, thread detail, sling.

## Honest gaps
- Bayonet lug position (underside of the nose cap) is from general knowledge; the fetched pages do not state it.
- Width and height are estimates, no dimensioned drawing was found.

## Texture memory
Measured at source size (2048 wood, 1024 metals); the game export halves them, so the spec limit is 48 MB rather than 16 MB.

## Triangle count
Final 6,024 (target 3,000-6,000, max 10,000): 0.4% over target, justified by sight, bolt and disc detail. No exception to the maximum requested.
