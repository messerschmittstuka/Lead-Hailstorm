# veg_shrubs - reference specification

Ground-level shrubs for the European maps (Normandy bocage, Lorraine, Ardennes, Kursk edges, Seelow). Class small_prop, budget for the four pieces together 800-3,000 triangles (max 4,500). Front axis -Y. Pieces stand at z = 0 on a 2.5 m layout. Soft vegetation: no collision (walk-through, bullets pass).

## Pieces
| piece | role | height (m) |
|---|---|---|
| shrub_bare_a, shrub_bare_b | winter / burnt scrub: multi-stem, bare, thorny hedgerow shrub (blackthorn or hazel in winter) | 1.1-1.6 |
| shrub_leafy_a, shrub_leafy_b | summer hedgerow shrub (hazel / hawthorn type) with leafy twig cards | 1.0-1.8 |

## Sources (what was actually read)
- Hedgerow guides (Countryfile, Woodland Trust, Wildlife Trusts, Conservation Handbooks): hazel is a multi-stemmed, wide, upright large shrub; hawthorn has a dense, thorny, rounded crown with spiny twigs; blackthorn bushes in hedges reach 1-3 m, thickly branched from the ground, bare spiny twigs in winter; hazel leaves heart-shaped, toothed; hawthorn leaves oval with deep lobes.
- The game height of 1.0-1.8 m is a hedge-trimmed / browsed shrub, deliberately lower than the free-growing species (blackthorn up to 7 m, hawthorn 5-7 m).

## Features that must be present
1. Several stems rising from a small footprint, branching, with real twig taper (no cylinders of one thickness).
2. Bare shrubs: forked twigs, thorn-like spurs allowed, bark texture, no leaf cards.
3. Leafy shrubs: leaf mass reads as a rounded hedgerow shrub with gaps showing stems; leaf cards of varied size, not a repeated pattern.
4. Silhouette from every side, no empty views (cards crossed or V-tilted).
5. All parts image-textured (bark, leaf cards with alpha).

## Deliberately omitted
Berries, catkins, blossom, individual leaf geometry, collision.

## Budget
Budget is per piece (small_prop target 500-2,000): four pieces together 800-4,800 triangles, hard maximum 8,000. No exception requested.
