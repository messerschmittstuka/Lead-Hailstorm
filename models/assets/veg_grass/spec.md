# veg_grass - reference specification

Ground cover tufts instanced by the thousand on every map. Class small_prop, budget for the seven pieces together 300-1,500 triangles (max 2,500; they are alpha cards, so cheap in triangles but expensive in overdraw). Front axis -Y. Pieces stand at z = 0 on a 2.5 m layout. No collision.

## Pieces
| piece | role | height (m) |
|---|---|---|
| grass_dry_short, grass_dry_tall | winter / steppe dry grass | 0.35-0.6 / 0.8-1.1 |
| grass_green_short, grass_green_tall | summer meadow grass | 0.4-0.7 / 0.8-1.1 |
| grass_meadow_flowers | meadow grass with flower heads | 0.7-1.0 |
| fern_clump | bracken-type fern, triangular fronds | 0.8-1.2 |
| reed_clump | common reed stand | 1.8-2.6 |

## Sources (what was actually read)
- Cocksfoot (Woodland Trust, JSTOR flora): dense tussocks 20-140 cm; leaf blades 10-45 cm long, 2-14 mm wide, bluish green; seedhead dense then open and branched.
- Meadow fescue (Bayer crop science): bright green, hairless blades up to 4 mm wide, up to 120 cm tall. Meadow foxtail 30-120 cm.
- Bracken (Natural England, RHS, Wildlife Trusts): fronds usually 100-200 cm, huge triangular finely divided leaves; dead fronds stay orange-brown through winter.
- Common reed (NZ Flora, USDA, Colorado): 1.5-3 m (up to 4-5 m in the best stands), flat strap leaves 1.3-5 cm wide tapering to a long tip, plume-like drooping seedhead.
- The game's 0.35-1.1 m tufts are mid-height tussocks; reed 2.2 m is the low end for a stand.

## Features that must be present
1. Several arching blades per tuft, tapering to a point, with natural lean and varied length (not a symmetric fan).
2. Tufts read from every side and from above (no flat single plane).
3. Dry grass: straw to tan, some darker tips; green grass: two greens; meadow: flower heads on stems above the blades.
4. Fern: frond silhouette fine and triangular, fronds radiating from a crown and arching.
5. Reed: tall straight stems with strap leaves and a drooping plume, narrower at the top.
6. Alpha-cut cards with image textures; backface culling off.

## Deliberately omitted
Individual blades as geometry, collision, seed detail.

## Texture memory
Seven 1024 px RGBA cards measure 35.9 MB at source size with mips; the game export halves them, so the limit here is 40 MB.
