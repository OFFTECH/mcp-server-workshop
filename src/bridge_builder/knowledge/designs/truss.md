## How it carries load

The deck (y=3) and the top chord (y=5) act as the two flanges of one deep beam.
Posts and diagonals split the space between them into triangles. A triangle of
pinned beams cannot change shape unless a member stretches, so the train's
weight turns into pull and push along the beams instead of bending at the joints.
The top chord works in compression. The end diagonals close the last triangle at
each end: without them the whole truss hangs from a single deck beam at each
anchor, and a pinned beam can swing, so the truss would drop and sway.

## Key geometry

- Deck: y=3 from the anchor at x=-6 to the anchor at x=6 (6 beams).
- Posts: x=-4, -2, 0, 2, 4, from y=3 up to y=5.
- Top chord: y=5 from x=-4 to x=4.
- Diagonals: from each deck node (x, 3) up to (x+2, 5) for x=-4..2, all leaning the same way.
- End diagonals: (-6,3)->(-4,5) and (6,3)->(4,5), from the anchors up to the top chord.
- Build order: deck from the left anchor, then posts, top chord, diagonals, end diagonals.

## When to choose it

The default answer: simple, robust, and moderately priced. Both anchors are fixed
pins, so the truss also leans on them like a shallow arch: the end diagonals are
pushed hardest, and being long (2.83 m) they buckle at half the push a 2 m beam
takes. Keep those two steel if you want wood elsewhere: with wood everywhere except
the two end diagonals the truss still crosses (2480, as wood costs more per beam
than steel). All wood snaps.
