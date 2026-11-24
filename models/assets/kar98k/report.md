# kar98k - final quality report

Status: **awaiting user approval** (nothing exported, nothing integrated).

- Versions built: 5 (improvement cycles used: 4 of 5)
- Loop verdict: 1 open defects (0 major), 0 failed checks
- Final triangles: 6024 (budget 3000-6000, max 10000)

## Triangle count by version

- v1: 19204
- v2: 6648
- v3: 6704
- v4: 5912
- v5: 6024

## Numeric checks (latest version)

- [WARN] triangle budget: 6024 tris (target 3000-6000, max 10000)  above target but under max: needs justification
- [PASS] dimension x: 0.099 m (spec 0.090 +-0.015 m)
- [PASS] dimension y: 1.115 m (spec 1.110 +-0.020 m)
- [PASS] dimension z: 0.223 m (spec 0.215 +-0.030 m)
- [PASS] materials textured: all materials use image textures
- [PASS] uv maps: all meshes have UVs
- [PASS] loose geometry: 0 loose vertices
- [PASS] zero-area faces: 0
- [PASS] origin: weapon origin on the bore axis by game contract (lowest point z = -0.130 m)
- [PASS] texture memory: 42.6 MB (mips included)

## Defect flow

- v2: 0 resolved, 0 new, 9 open
- v3: 3 resolved, 0 new, 6 open
- v4: 2 resolved, 1 new, 5 open
- v5: 2 resolved, 0 new, 3 open

## Remaining open defects

- D9 [minor/materials] Blued parts carry long white hair-like scratches and chip blotches from the shared gun texture; real blued steel wears at edges. Not fixable in geometry.
