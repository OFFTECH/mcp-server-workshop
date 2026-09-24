"""Reference trusses as plain beam lists, for tests and the notebook spoiler.

The designs themselves live in ``knowledge/designs/`` (see ``designs.py``);
these lists are derived from those files.
"""

from bridge_builder.designs import get_design

TRUSS_GIRDERS: list[tuple[float, float, float, float]] = [b[:4] for b in get_design("truss").beams]

# Inverted (under-deck) truss: the bottom chord hangs at y=1 inside the gap.
INVERTED_TRUSS: list[tuple[float, float, float, float, str]] = get_design("inverted_truss").beams
