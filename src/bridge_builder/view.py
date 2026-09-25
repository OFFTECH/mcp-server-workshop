"""Pygame window, camera, mouse tools, HUD."""

from __future__ import annotations

import math
from collections.abc import Callable

import pygame
from Box2D import b2CircleShape, b2MouseJointDef, b2PolygonShape, b2Vec2

from bridge_builder.api import GameAPI
from bridge_builder.game import Game
from bridge_builder.grid import GAP_FLOOR_Y, GAP_X, GRID, aim_member, iter_grid_points, snap_mouse
from bridge_builder.materials import DEFAULT_MATERIAL, MATERIAL_ORDER, MATERIALS
from bridge_builder.physics import CHASSIS_SIZE, DT, GIRDER_THICKNESS

WIDTH, HEIGHT = 1280, 720  # the canvas everything is drawn on, in canvas pixels
PPM = 40.0
# The window shows the canvas scaled down, so it fits half of a 1920 px wide screen.
WINDOW_SCALE = 0.72
WINDOW_SIZE = (round(WIDTH * WINDOW_SCALE), round(HEIGHT * WINDOW_SCALE))
VIEW_LEFT, VIEW_BOTTOM = -16.0, -2.0
SKY_TOP = (226, 228, 232)  # soft grey gradient, no pure white
SKY_BOTTOM = (178, 182, 190)
BANK = (80, 80, 84)
GIRDER = (50, 50, 55)
CHASSIS = (0, 60, 101)  # FETNIS dark blue
WHEEL = (20, 20, 20)
TRAIN_LABEL = "FETNIS"
TRAIN_LABEL_COLOR = (255, 255, 255)
HUD = (20, 20, 20)
RUBBER = (255, 255, 255)
RUBBER_BAD = (180, 40, 40)
GRID_MAJOR = (120, 140, 175)
GRID_DOT = (60, 70, 90)
SNAP = (255, 60, 60)
SNAP_OK = (40, 220, 80)
ANCHOR = (220, 40, 40)
NODE = (250, 250, 250)
NODE_EDGE = (30, 30, 35)
HIGHLIGHT = (205, 95, 0)  # dark orange: selected material
GRID_TOP_Y = 13.0  # mesh stops here; the band above is reserved for the HUD text
HUD_HEIGHT = 96  # px from the top used by the three HUD lines

TOOL_KEYS = {
    pygame.K_b: "girder",
    pygame.K_j: "joint",
    pygame.K_g: "grab",
    pygame.K_d: "destroy",
}
MATERIAL_KEYS = {
    pygame.K_1: "wood",
    pygame.K_2: "steel",
    pygame.K_3: "titanium",
}


def next_material(current: str) -> str:
    """The grade after ``current`` in MATERIAL_ORDER, wrapping around (M key)."""
    idx = MATERIAL_ORDER.index(current) if current in MATERIAL_ORDER else -1
    return MATERIAL_ORDER[(idx + 1) % len(MATERIAL_ORDER)]


def world_to_screen(x: float, y: float) -> tuple[int, int]:
    sx = int((x - VIEW_LEFT) * PPM)
    sy = int(HEIGHT - (y - VIEW_BOTTOM) * PPM)
    return sx, sy


def screen_to_world(sx: int, sy: int) -> tuple[float, float]:
    x = sx / PPM + VIEW_LEFT
    y = (HEIGHT - sy) / PPM + VIEW_BOTTOM
    return x, y


def window_to_canvas(pos: tuple[int, int]) -> tuple[int, int]:
    """A mouse position in the (scaled) window, in canvas pixels."""
    return round(pos[0] / WINDOW_SCALE), round(pos[1] / WINDOW_SCALE)


def _kind(body) -> str:
    data = body.userData or {}
    return str(data.get("kind", ""))


_sky_cache: pygame.Surface | None = None


def sky_surface() -> pygame.Surface:
    """Window-sized vertical gradient from SKY_TOP to SKY_BOTTOM, built once."""
    global _sky_cache
    if _sky_cache is not None and _sky_cache.get_size() == (WIDTH, HEIGHT):
        return _sky_cache
    surf = pygame.Surface((WIDTH, HEIGHT))
    for row in range(HEIGHT):
        t = row / max(HEIGHT - 1, 1)
        color = tuple(int(round(a + (b - a) * t)) for a, b in zip(SKY_TOP, SKY_BOTTOM))
        pygame.draw.line(surf, color, (0, row), (WIDTH - 1, row))
    _sky_cache = surf
    return surf


def run(
    game: Game,
    api: GameAPI | None = None,
    mcp_ok: Callable[[], bool] | None = None,
    max_frames: int | None = None,
) -> None:
    pygame.init()
    pygame.display.set_caption("Bridge Builder")
    window = pygame.display.set_mode(WINDOW_SIZE)
    screen = pygame.Surface((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 28)
    tool = "girder"
    material = DEFAULT_MATERIAL
    drag_start: tuple[float, float] | None = None
    mouse_joint = None
    frames = 0
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in TOOL_KEYS:
                    tool = TOOL_KEYS[event.key]
                    drag_start = None
                    _clear_mouse_joint(game, mouse_joint)
                    mouse_joint = None
                elif event.key in MATERIAL_KEYS:
                    material = MATERIAL_KEYS[event.key]
                elif event.key == pygame.K_m:
                    material = next_material(material)
                elif event.key == pygame.K_SPACE:
                    game.toggle_pause()
                elif event.key == pygame.K_t:
                    game.start_train(force=True)
                elif event.key == pygame.K_r:
                    _clear_mouse_joint(game, mouse_joint)
                    mouse_joint = None
                    game.reset()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                wx, wy = snap_mouse(*screen_to_world(*window_to_canvas(event.pos)))
                if event.button == 3:
                    drag_start = None
                    _clear_mouse_joint(game, mouse_joint)
                    mouse_joint = None
                elif event.button == 1:
                    if tool == "girder":
                        if game.world.has_node(wx, wy):
                            drag_start = (wx, wy)
                    elif tool == "joint":
                        game.add_joint(wx, wy)
                    elif tool == "destroy":
                        game.destroy_at(*screen_to_world(*window_to_canvas(event.pos)), snap=False)
                    elif tool == "grab":
                        mouse_joint = _grab(game, wx, wy)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and tool == "girder" and drag_start is not None:
                    mx, my = screen_to_world(*window_to_canvas(event.pos))
                    member = aim_member(drag_start[0], drag_start[1], mx, my)
                    if member is not None:
                        game.place_girder(*member, material=material)
                    drag_start = None
                if event.button == 1 and tool == "grab":
                    _clear_mouse_joint(game, mouse_joint)
                    mouse_joint = None
            elif event.type == pygame.MOUSEMOTION:
                if tool == "destroy" and event.buttons[0]:
                    game.destroy_at(*screen_to_world(*window_to_canvas(event.pos)), snap=False)
                if mouse_joint is not None:
                    wx, wy = screen_to_world(*window_to_canvas(event.pos))
                    if isinstance(mouse_joint, tuple):
                        game.world.drag_node(mouse_joint[1], (wx, wy))
                    else:
                        mouse_joint.target = b2Vec2(wx, wy)

        if api is not None:
            api.drain()
        game.step()

        screen.blit(sky_surface(), (0, 0))
        _draw_grid(screen)
        _draw_world(screen, game)
        _draw_nodes(screen, game)
        mx, my = screen_to_world(*window_to_canvas(pygame.mouse.get_pos()))
        if tool == "destroy":
            _draw_delete_cursor(screen, game, mx, my)
        else:
            sx, sy = snap_mouse(mx, my)
            snap_col = SNAP_OK if game.world.has_node(sx, sy) else SNAP
            pygame.draw.circle(screen, snap_col, world_to_screen(sx, sy), 8, 2)
        if drag_start is not None:
            member = aim_member(drag_start[0], drag_start[1], mx, my)
            if member is not None:
                pygame.draw.line(
                    screen,
                    MATERIALS[material].color,
                    world_to_screen(member[0], member[1]),
                    world_to_screen(member[2], member[3]),
                    max(2, int(GIRDER_THICKNESS * PPM)),
                )
            else:
                pygame.draw.circle(screen, RUBBER_BAD, world_to_screen(*drag_start), 8, 2)
        _draw_hud(screen, font, game, tool, material, mcp_ok)
        pygame.transform.smoothscale(screen, WINDOW_SIZE, window)
        pygame.display.flip()
        clock.tick(int(1.0 / DT))
        frames += 1
        if max_frames is not None and frames >= max_frames:
            break

    _clear_mouse_joint(game, mouse_joint)
    pygame.quit()


def _draw_grid(screen: pygame.Surface) -> None:
    for x, y in iter_grid_points(y_max=GRID_TOP_Y):
        pygame.draw.circle(screen, GRID_DOT, world_to_screen(x, y), 3)
    y0 = 3.0
    x = -16.0
    while x <= 16.0 + 1e-6:
        # inside the gap the grid continues below the deck, down to the floor
        y_bottom = GAP_FLOOR_Y if GAP_X[0] < x < GAP_X[1] else y0
        pygame.draw.line(
            screen,
            GRID_MAJOR,
            world_to_screen(x, y_bottom),
            world_to_screen(x, GRID_TOP_Y),
            1,
        )
        x += GRID
    y = GAP_FLOOR_Y
    while y < y0 - 1e-6:
        pygame.draw.line(
            screen,
            GRID_MAJOR,
            world_to_screen(GAP_X[0], y),
            world_to_screen(GAP_X[1], y),
            1,
        )
        y += GRID
    y = y0
    while y <= GRID_TOP_Y + 1e-6:
        pygame.draw.line(
            screen,
            GRID_MAJOR,
            world_to_screen(-16.0, y),
            world_to_screen(16.0, y),
            1,
        )
        y += GRID


def _draw_nodes(screen: pygame.Surface, game: Game) -> None:
    for node, (x, y) in game.world.iter_nodes():
        if node in game.world.anchors:
            pygame.draw.circle(screen, ANCHOR, world_to_screen(x, y), 9)
            pygame.draw.circle(screen, (255, 180, 180), world_to_screen(x, y), 9, 2)
        else:
            pygame.draw.circle(screen, NODE, world_to_screen(x, y), 6)
            pygame.draw.circle(screen, NODE_EDGE, world_to_screen(x, y), 6, 2)


def _grab(game: Game, x: float, y: float):
    """Grab tool: pull a bridge node (it bends the truss) or, failing that, a train car or debris."""
    node = game.world.grab_node(x, y)
    if node is not None:
        game.world.drag_node(node, (x, y))
        return ("node", node)
    bodies = game.world.bodies_at(x, y)
    dynamic = [b for b in bodies if b.type == 2]
    if not dynamic:
        return None
    body = dynamic[0]
    md = b2MouseJointDef()
    md.bodyA = game.world.left_bank
    md.bodyB = body
    md.target = b2Vec2(x, y)
    md.maxForce = 1000.0 * body.mass
    md.frequencyHz = 6.0
    md.dampingRatio = 0.7
    return game.world.world.CreateJoint(md)


def _clear_mouse_joint(game: Game, joint) -> None:
    if joint is None:
        return
    if isinstance(joint, tuple):  # a dragged bridge node
        game.world.drag_node(None)
        return
    try:
        game.world.world.DestroyJoint(joint)
    except Exception:
        pass


def load_color(load: float) -> tuple[int, int, int]:
    """Green at no load, through yellow, to red at the beam's limit."""
    t = min(1.0, max(0.0, load))
    return (int(20 + 235 * t), int(220 * (1.0 - t)), 20)


def _draw_world(screen: pygame.Surface, game: Game) -> None:
    for body in game.world.iter_bodies():
        kind = _kind(body)
        if kind == "bank":
            color = BANK
        elif kind == "chassis":
            color = CHASSIS
        elif kind == "wheel":
            color = WHEEL
        elif kind == "girder":
            grade = MATERIALS.get((body.userData or {}).get("material", ""))
            color = grade.color if grade is not None else GIRDER
        else:
            color = GIRDER
        for fixture in body.fixtures:
            shape = fixture.shape
            if isinstance(shape, b2PolygonShape):
                verts = [body.transform * v for v in shape.vertices]
                pts = [world_to_screen(v.x, v.y) for v in verts]
                if len(pts) >= 3:
                    pygame.draw.polygon(screen, color, pts)
            elif isinstance(shape, b2CircleShape):
                center = body.transform * shape.pos
                r = max(2, int(shape.radius * PPM))
                pygame.draw.circle(screen, color, world_to_screen(center.x, center.y), r)

    _draw_train_labels(screen, game)

    # each intact beam's pull or push, as a share of its limit, along its centre line
    for gid in game.world.iter_beams():
        (ax, ay), (bx, by) = game.world.structure.member_ends(gid)
        color = load_color(game.world.beam_load(gid))
        pygame.draw.line(screen, color, world_to_screen(ax, ay), world_to_screen(bx, by), 3)


def _draw_delete_cursor(screen: pygame.Surface, game: Game, mx: float, my: float) -> None:
    """Delete tool: outline the beam under the mouse in red, plus a small cross at the cursor."""
    body = game.world.girder_at(mx, my)
    if body is not None:
        for fixture in body.fixtures:
            shape = fixture.shape
            if isinstance(shape, b2PolygonShape):
                pts = [world_to_screen(v.x, v.y) for v in (body.transform * v for v in shape.vertices)]
                if len(pts) >= 3:
                    pygame.draw.polygon(screen, SNAP, pts, 3)
    cx, cy = world_to_screen(mx, my)
    pygame.draw.line(screen, SNAP, (cx - 7, cy - 7), (cx + 7, cy + 7), 2)
    pygame.draw.line(screen, SNAP, (cx - 7, cy + 7), (cx + 7, cy - 7), 2)


_label_cache: dict[tuple[str, int], pygame.Surface] = {}


def _draw_train_labels(screen: pygame.Surface, game: Game) -> None:
    """Write TRAIN_LABEL across every chassis, rotated with the car."""
    for body in game.world.iter_bodies():
        if _kind(body) != "chassis":
            continue
        key = (TRAIN_LABEL, int(CHASSIS_SIZE[1] * PPM * 0.7))
        base = _label_cache.get(key)
        if base is None:
            base = pygame.font.Font(None, key[1]).render(TRAIN_LABEL, True, TRAIN_LABEL_COLOR)
            _label_cache[key] = base
        rotated = pygame.transform.rotate(base, math.degrees(body.angle))
        cx, cy = world_to_screen(body.position.x, body.position.y)
        screen.blit(rotated, rotated.get_rect(center=(cx, cy)))


def _draw_hud(
    screen: pygame.Surface,
    font: pygame.font.Font,
    game: Game,
    tool: str,
    material: str,
    mcp_ok: Callable[[], bool] | None,
) -> None:
    st = game.status()
    if st.get("error"):
        phase = "PHYSICS ERROR"
    elif mcp_ok is not None and not mcp_ok():
        phase = "MCP OFFLINE"
    elif st["train"] == "win":
        phase = "WIN"
    elif st["train"] == "lose":
        phase = "LOSE"
    elif st["paused"]:
        phase = "PAUSED"
    else:
        phase = "RUNNING"
    score = st["score"]
    score_txt = "—" if score is None else str(score)
    line = (
        f"Cost: {st['cost']}/{st['budget']}  Remaining: {st['remaining']}  "
        f"Score: {score_txt}    Peak load: {st['peak_load']:.0%}    [{phase}]    Tool: {tool}"
    )
    hint = hud_hint(phase)
    screen.blit(font.render(line, True, HUD), (16, 12))
    small = pygame.font.Font(None, 22)
    x = 16
    for text, color in material_segments(material):
        surf = small.render(text, True, color)
        screen.blit(surf, (x, 42))
        x += surf.get_width()
    screen.blit(small.render(hint, True, HUD), (16, 66))


def hud_hint(phase: str) -> str:
    """Bottom HUD line. After a test, tell the player how to run it again."""
    if phase in ("WIN", "LOSE"):
        return (
            f"{phase}: Space = rebuild and run the train again  "
            "B = beam  D = delete  R = clear everything"
        )
    return (
        "Red = anchors. B: click a node, drag to a neighbour. D = delete (click a beam).  "
        "1/2/3 or M = material  Space = train  R = reset"
    )


def material_segments(selected: str) -> list[tuple[str, tuple[int, int, int]]]:
    """The material picker line as (text, colour) runs; only the selected grade is HIGHLIGHT."""
    segments: list[tuple[str, tuple[int, int, int]]] = [("Material:  ", HUD)]
    for i, name in enumerate(MATERIAL_ORDER):
        grade = MATERIALS[name]
        label = f"[{i + 1}] {name} {grade.cost} / {grade.strength:g}x"
        segments.append((label, HIGHLIGHT if name == selected else HUD))
        if i < len(MATERIAL_ORDER) - 1:
            segments.append(("     ", HUD))
    return segments
