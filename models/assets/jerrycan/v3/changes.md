# v3 changes (from v2)

Defects addressed:

Addresses D2, D6, D10 (the three that can be fixed in geometry). D4 (rust-splash paint texture) is deliberately NOT changed: it needs a new purpose-made can paint texture, which is outside this loop test, and re-scaling the shared texture would just be a cosmetic guess.
- D2: handle 30 mm deep, posts 14 mm, top bar 10 mm, taller openings.
- D6: two extra loops at y = +-5.5 mm before the groove displacement (groove 4.5 mm deep, 11 mm wide, continuous).
- D10: body depth 0.165 -> 0.156 m so that over the ribs it is 0.165 m.
