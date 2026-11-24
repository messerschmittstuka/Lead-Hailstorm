# german_soldier_e - reference specification

Wehrmacht rifleman, Eastern Front, summer 1943 (Kursk). One rigged, textured character with idle, walk and run clips, built to replace the box soldiers the game builds in code. Class small_prop with a character budget (6,000-14,000 tris, max 18,000).

## Sources
- Field tunic: M43 pattern has straight (unpleated) pockets, six buttons, a deeper grey than earlier models, and shortened skirts (historyofwar.org, "German M43 Field Tunic"). Four patch pockets and field-grey painted buttons are the main recognition features (historyofwar.org, German Army Equipment).
- Webbing: a leather waist belt with Y-straps over the shoulders; the straps hook onto D-rings on the back of the ammunition pouches (smore.com German Infantryman; IWM object 30016126).
- Pouches: Kar98k triple ammunition pouches in black pebble-grain leather (IMA field gear listing). Pouch position: inside edges in line with the tunic pockets and no more than three finger widths from the buckle (reenactor.net, Wear of Uniform and Equipment).
- Kit carried by a rifleman: belt, Y-straps, pouches, bayonet and entrenching tool, bread bag, canteen, gas mask canister (IMA listing; miniatures.de Sturmgepack; festung.net Soldbuch issue list).
- Footwear: Schnuerschuhe ankle boots (warfarehistorynetwork.com).

## Dimensions
Height to top of helmet about 1.80 m, shoulders about 0.40 m wide, boots on z = 0.

## Features that must be present
1. Believable human proportions, sculpted head with brow, nose, lips, chin, ears, painted eyes, stubble and hair.
2. Feldgrau wool tunic with four patch pockets, collar, shoulder straps, buttons; trousers bloused into ankle boots.
3. Stahlhelm with chin strap and ventilation rivets.
4. Leather belt, buckle, two triple ammo pouches, Y-straps (front and back), bread bag, canteen, gas mask canister.
5. Skeleton with Mixamo-style names (Hips, Spine, Spine1, Spine2, Neck, Head, Left/RightShoulder, Arm, ForeArm, Hand, UpLeg, Leg, Foot, ToeBase) so the game's bone lookups work. Clips named idle, walk, run.

## Deliberately omitted
Fingers (mitten hand with thumb), facial animation, individual stitching, the rifle (the game attaches its own).

## Pass 2 (face and uniform)
Reference photo supplied by the user (a period soldier portrait): lighter, ruddy clean-shaven skin, grey-blue eyes, high cheekbones, short straight nose, thin lips, prominent ears; dark bottle-green collar with two-bar collar tabs, piped shoulder straps, scalloped buttoned pocket flaps, eagle breast patch, belt buckle plate. Baseline v1 = german_soldier v5.

## Pass 3 (shared face polish)
Keep one procedural face for every soldier; correct proportions against the reference photo: narrower oval head, wider mouth, eye width about equal to the gap between the eyes, straighter heavier brows, jaw-angle definition, highlights on forehead/nose/cheeks, neck tapering under the jaw. Baseline v1 = german_soldier_b v5.
