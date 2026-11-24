# veg_wheat - reference specification

Ripe winter wheat for the Kursk fields (July 1943). Class small_prop. One in-game clump (instanced thousands of times, so it must stay light) plus a 4 x 4 m patch preview used only to judge how the instanced field reads. Soft vegetation: no collision.

## Pieces
| piece | role | height (m) |
|---|---|---|
| wheat_clump | the instanced clump, about 0.5 m across, 7 crossed alpha cards | 0.8-1.15 |
| wheat_patch_preview | 50 randomly rotated clumps merged, review only, not exported | 0.8-1.2 |

## Sources (what was actually read)
- Winter wheat phenotyping descriptors (University of Minnesota, Genesys, Research Square, Frontiers): morphology is judged by plant height, stem (culm) diameter, flag leaf length and width, spike length and awn length. Variety height ranges from short semi-dwarfs to about 1.6 m in tall old lines (Research Square wheat study).
- 1943 landraces and old Soviet winter wheats were tall; the game uses 0.8-1.15 m so the player can crouch and be hidden.
- Typical dimensions (agronomy general knowledge, not from one page): culm 3-5 mm thick, ear (spike) 6-12 cm long and about 1-2 cm wide, awns 3-8 cm, flag leaf 10-15 mm wide and 15-25 cm long.

## Features that must be present
1. Thin straw culms with visible nodes, not box stalks.
2. Ears about 8-10 cm long with spikelets in two rows, golden glumes, long fine awns fanning out above, ears drooping slightly at maturity.
3. Straw-coloured stems, paler leaf sheaths, dried yellow-green leaves arching off the stem.
4. Colour variation between culms (golden, straw, a few greener), not one flat yellow.
5. Reads as a continuous field when instanced densely, from standing height and from prone.

## Deliberately omitted
Individual kernels in 3D, weeds (poppies, cornflowers), tractor tramlines, lodging patches.
