# FETNIS

A river crossing that ships can sail under, built with as much timber as the physics allows.

## Requirements, in priority order

1. **Clearance (must).** Ships pass through the gap below the road. No beam may
   hang below the deck: every beam inside the gap (x between -6 and 6) must have
   both ends at y >= 3. A design that hangs under the road, such as an inverted
   truss, is not acceptable at any price.
2. **Sustainability (strong preference).** We prefer timber. Choose the design
   with the highest wood share (wood beams divided by all beams). Use steel only
   where wood would fail.
3. **Cost (last).** Only between designs that are equal on 1 and 2 does the
   cheaper one win. We accept a higher price for more wood.
4. **Safety.** The train must cross with a peak beam load below 0.9.

## How to decide

- Start from the reference designs (`bridge://designs`). Check each one against
  the requirements: clearance from its beams (`bridge://designs/<name>/beams`),
  wood share from the materials of its beams, safety from its benchmark.
- A custom design is welcome if it beats every compliant reference design on
  the requirements above. Test it the same way before recommending it.

## Report

State the chosen design, its wood share, cost and peak load, and confirm that no
beam hangs below the deck. Name the cheapest design overall, say why it was not
chosen, and how much more our choice costs.
