from bridge_builder.game import Game
from bridge_builder.view import HEIGHT, WIDTH, run, screen_to_world, world_to_screen


def test_camera_roundtrip():
    for x, y in [(-16, -2), (16, 16), (0, 3), (-6, 3), (6, 3)]:
        sx, sy = world_to_screen(x, y)
        rx, ry = screen_to_world(sx, sy)
        assert abs(rx - x) < 0.05
        assert abs(ry - y) < 0.05


def test_left_bank_is_on_screen():
    sx, sy = world_to_screen(-10, 3)
    assert 0 < sx < WIDTH
    assert 0 < sy < HEIGHT


def test_loop_runs_headless():
    g = Game()
    run(g, max_frames=10)


def test_material_key_cycles_grades():
    from bridge_builder.materials import MATERIAL_ORDER
    from bridge_builder.view import next_material

    assert MATERIAL_ORDER == ["wood", "steel", "titanium"]
    assert next_material("wood") == "steel"
    assert next_material("steel") == "titanium"
    assert next_material("titanium") == "wood"


def test_theme_colours_and_train_label():
    from bridge_builder.view import BANK, CHASSIS, SKY_BOTTOM, SKY_TOP, TRAIN_LABEL

    # soft grey gradient: light at the top, darker at the bottom, no pure white
    assert 190 <= max(SKY_TOP) <= 240 and max(SKY_TOP) - min(SKY_TOP) < 16
    assert 150 <= max(SKY_BOTTOM) < max(SKY_TOP)
    assert max(BANK) < 110 and max(BANK) - min(BANK) < 10  # dark, neutral grey
    # FETNIS dark blue: blue channel dominates, overall dark
    assert CHASSIS[2] > CHASSIS[1] > CHASSIS[0] and CHASSIS[2] < 130
    assert TRAIN_LABEL == "FETNIS"


def test_sky_gradient_surface_matches_window():
    import pygame

    from bridge_builder.view import HEIGHT, WIDTH, SKY_BOTTOM, SKY_TOP, sky_surface

    pygame.init()
    sky = sky_surface()
    assert sky.get_size() == (WIDTH, HEIGHT)
    assert sky.get_at((0, 0))[:3] == SKY_TOP
    assert sky.get_at((0, HEIGHT - 1))[:3] == SKY_BOTTOM


def test_loop_draws_labelled_train_headless():
    g = Game()
    g.start_train()
    run(g, max_frames=5)


def test_material_line_highlights_only_selected():
    from bridge_builder.view import HIGHLIGHT, HUD, material_segments

    segs = material_segments("steel")
    assert [c for _t, c in segs].count(HIGHLIGHT) == 1
    assert all(c in (HUD, HIGHLIGHT) for _t, c in segs)
    assert HIGHLIGHT[0] > 150 and HIGHLIGHT[1] < 120 and HIGHLIGHT[2] < 40  # dark orange
    selected = [t for t, c in segs if c == HIGHLIGHT][0]
    assert "steel" in selected
    assert "wood" in "".join(t for t, c in segs if c == HUD)


def test_hud_text_sits_above_mesh():
    from bridge_builder.view import GRID_TOP_Y, HUD_HEIGHT, world_to_screen

    _sx, mesh_top = world_to_screen(0.0, GRID_TOP_Y)
    assert mesh_top >= HUD_HEIGHT


def test_hud_hint_mentions_delete_and_rerun():
    from bridge_builder.view import hud_hint

    assert "D = delete" in hud_hint("PAUSED")
    assert "again" in hud_hint("WIN").lower()
    assert "again" in hud_hint("LOSE").lower()


def test_load_colour_runs_green_to_red():
    from bridge_builder.view import load_color

    assert load_color(0.0) == (20, 220, 20)
    assert load_color(1.0) == (255, 0, 20)
    assert load_color(5.0) == load_color(1.0)


def test_window_fits_half_a_1920_screen():
    from bridge_builder.view import WINDOW_SIZE

    assert WINDOW_SIZE[0] + 20 <= 960  # room for the window frame
    assert abs(WINDOW_SIZE[0] / WINDOW_SIZE[1] - WIDTH / HEIGHT) < 0.01


def test_mouse_in_the_scaled_window_hits_the_same_grid_node():
    from bridge_builder.view import WINDOW_SCALE, window_to_canvas

    sx, sy = world_to_screen(-6, 3)  # the innermost left anchor, in canvas pixels
    in_window = (round(sx * WINDOW_SCALE), round(sy * WINDOW_SCALE))
    x, y = screen_to_world(*window_to_canvas(in_window))
    assert abs(x + 6) < 0.1 and abs(y - 3) < 0.1
