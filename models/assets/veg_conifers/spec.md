# veg_conifers - reference specification

Full-size conifers for the European maps: Scots pine, Norway spruce, snow-laden Norway spruce. Class large_prop, budget per tree 2,000-6,000 triangles (max 10,000). Front axis -Y. Pieces stand at z = 0 on an 11 m layout. Each tree has a closed low-poly COL_ trunk collision hull; foliage is walk-through.

## Pieces
| piece | height (m) |
|---|---|
| tree_pine_a / tree_pine_b | 16-20 / 13-17 (Scots pine) |
| tree_spruce_a / tree_spruce_b | 14-18 / 10-14 (Norway spruce) |
| tree_spruce_snow_a / _b | same spruces with snow on the branches |

## Sources (what was actually read)
- Scots pine (Virginia Tech Dendrology, NC State Extension, Trees and Shrubs Online, USU): paired stiff twisted blue-green needles 4-7 cm; bark orange and thin / flaking in the upper trunk and crown, grey to red-brown ridged plates low on the trunk; trunk often twisted or poorly formed; young crown rounded, old crown broad, irregular and round-topped; up to about 30 m.
- Norway spruce (Uni Hamburg Earle, UVM, Stony Brook, Cornell, realchristmastrees): conical crown, whorled branches drooping in the lower tiers and ascending in the top tier, long pendulous branchlets, dark green 1-2.5 cm four-sided needles, orange-brown bark becoming grey-brown and scaly, long hanging cones 10-15 cm.

## Features that must be present
1. Pine: long bare trunk with a visible bark change (grey-brown plates low, orange flaking up high), a few heavy irregular limbs, foliage in clumps at the branch ends, crown flat or round-topped.
2. Spruce: straight trunk, regular whorls, lower tiers drooping with upturned tips, upper tier ascending, conical outline with a pointed leader; dead stubs on the lower trunk.
3. Snow spruce: same form with snow on the upper surfaces of the branches, dark underside showing.
4. Needle foliage as alpha cards with real needle detail (not flat colour), V-tilted so no empty view.
5. Closed COL_ hull of the trunk for each tree; all parts image-textured.

## Deliberately omitted
Cones, individual needles, resin, bark insects, and trunk lean beyond about 5 degrees.
