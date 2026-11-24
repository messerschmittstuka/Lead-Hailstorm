# jerrycan - final quality report

Status: **awaiting user approval** (nothing exported, nothing integrated).

- Versions built: 3 (improvement cycles used: 2 of 5)
- Loop verdict: 1 open defects (0 major), 0 failed checks
- Final triangles: 1172 (budget 500-2000, max 3000)

## Triangle count by version

- v1: 364
- v2: 1068
- v3: 1172

## Numeric checks (latest version)

- [PASS] triangle budget: 1172 tris (target 500-2000, max 3000)
- [PASS] dimension x: 0.350 m (spec 0.350 +-0.012 m)
- [PASS] dimension y: 0.165 m (spec 0.165 +-0.008 m)
- [PASS] dimension z: 0.463 m (spec 0.460 +-0.012 m)
- [PASS] materials textured: all materials use image textures
- [PASS] uv maps: all meshes have UVs
- [PASS] loose geometry: 0 loose vertices
- [PASS] zero-area faces: 0
- [PASS] sits on ground (z=0): lowest point z = 0.000 m
- [PASS] collision hull: closed, 24 tris
- [WARN] texture memory: 21.3 MB (mips included)

## Defect flow

- v2: 5 resolved, 1 new, 4 open
- v3: 0 resolved, 0 new, 4 open

## Remaining open defects

- D4 [minor/materials] Rust splashes still read as camouflage blotches (shared baked texture).
