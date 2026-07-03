"""Textual pilot tests for the dual-pane PreviewApp layout."""

from functools import partial

from helpers import make_app as _make_app
from textual.widgets import Static

from terminal_velocity.preview import PreviewApp, _human_size

make_app = partial(_make_app, app_cls=PreviewApp)


def preview_text(app):
    return app.query_one("#preview", Static).render().plain


def stats_text(app):
    return app.query_one("#stats-bar", Static).render().plain


async def test_preview_shows_highlighted_note(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"apples")
        assert app.highlighted_note.title == "applesauce"
        assert preview_text(app) == "also apples"
        stats = stats_text(app)
        assert "applesauce" in stats
        assert "1 line " in stats and "modified" in stats


async def test_preview_updates_on_navigation(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"apple")
        first = preview_text(app)
        await pilot.press("down")
        assert preview_text(app) != first
        assert preview_text(app) == app.highlighted_note.contents


async def test_preview_clears_when_highlight_cleared(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"apples")
        assert preview_text(app)
        await pilot.press("escape")
        assert app.highlighted_note is None
        assert preview_text(app) == ""
        assert stats_text(app) == ""


async def test_preview_strips_control_chars_keeps_newlines(notes_dir):
    (notes_dir / "tricky.txt").write_text("line one\n\x1b[2Jline two\ttabbed")
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"tricky")
        text = preview_text(app)
        assert "\x1b" not in text
        assert "line one\n" in text and "\ttabbed" in text


async def test_search_and_create_inherited(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        assert [n.title for n in app.matches] == ["banana"]
        await pilot.press("escape", "escape")
        await pilot.press(*"fresh note")
        await pilot.press("enter")
        assert (notes_dir / "fresh note.txt").exists()


async def test_shift_keys_scroll_preview(notes_dir):
    (notes_dir / "long.txt").write_text("line\n" * 100)
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"long")
        scroll = app.query_one("#preview-scroll")
        assert scroll.scroll_y == 0
        await pilot.press("shift+down")
        assert scroll.scroll_y == 1
        await pilot.press("shift+pagedown")
        assert scroll.scroll_y == 11
        await pilot.press("shift+up")
        assert scroll.scroll_y == 10


async def test_preview_pane_cannot_steal_focus(notes_dir):
    from textual.widgets import Input

    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press("shift+tab")
        assert isinstance(app.focused, Input)
        await pilot.click("#preview-scroll")
        assert isinstance(app.focused, Input)


async def test_stats_line_count_matches_wc(notes_dir):
    (notes_dir / "counted.txt").write_text("one\ntwo\nthree\n")
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"counted")
        assert "3 lines" in stats_text(app)


async def test_shift_home_end_jump_preview(notes_dir):
    (notes_dir / "long.txt").write_text("line\n" * 100)
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"long")
        scroll = app.query_one("#preview-scroll")
        await pilot.press("shift+end")
        assert scroll.scroll_y == scroll.max_scroll_y > 0
        await pilot.press("shift+home")
        assert scroll.scroll_y == 0


async def test_wheel_over_nonscrollable_area_scrolls_preview(notes_dir):
    from textual.events import MouseScrollDown
    from textual.widgets import Input

    (notes_dir / "long.txt").write_text("line\n" * 100)
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"long")
        scroll = app.query_one("#preview-scroll")
        # Post to the Input (the non-scrollable widget under the pointer) so
        # the event must bubble up to the app handler, exercising the real
        # forwarding path rather than calling the handler directly.
        inp = app.query_one(Input)
        r = inp.region
        x, y = r.x + 2, r.y + 1
        inp.post_message(
            MouseScrollDown(
                widget=inp,
                x=x,
                y=y,
                delta_x=0,
                delta_y=1,
                button=0,
                shift=False,
                meta=False,
                ctrl=False,
                screen_x=x,
                screen_y=y,
            )
        )
        await pilot.pause()
        assert scroll.scroll_y > 0


async def test_ctrl_r_refreshes_preview_on_content_preserving_edit(notes_dir):
    import os

    p = notes_dir / "note.txt"
    p.write_text("aaaa")
    os.utime(p, (1000, 1000))
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"note")
        assert preview_text(app) == "aaaa"
        # Same length, same mtime: only a forced re-read can catch it.
        p.write_text("bbbb")
        os.utime(p, (1000, 1000))
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert preview_text(app) == "bbbb"


async def test_stats_bar_sanitizes_path(notes_dir):
    # The title is sanitized in scan, but the raw path could carry control
    # bytes from the filename; the stats line must strip them too.
    (notes_dir / "e\x1bvil.txt").write_text("body")
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"evil")
        assert "\x1b" not in stats_text(app)


async def test_stats_bar_shows_path(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        assert str(notes_dir / "banana.txt") in stats_text(app)


async def test_bars_match_and_stand_out_from_background(notes_dir):
    from textual.widgets import Input

    app = make_app(notes_dir)
    async with app.run_test():
        input_bg = app.query_one(Input).styles.background
        stats_bg = app.query_one("#stats-bar", Static).styles.background
        screen_bg = app.screen.styles.background
        assert input_bg == stats_bg
        assert input_bg != screen_bg


async def test_typing_preserves_scroll_when_note_unchanged(notes_dir):
    (notes_dir / "long.txt").write_text("line\n" * 100)
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"long")
        scroll = app.query_one("#preview-scroll")
        await pilot.press("shift+down", "shift+down", "shift+down")
        assert scroll.scroll_y == 3
        # Backspace keeps "lon" prefix-matching the same note; the reader's
        # position must survive the refilter.
        await pilot.press("backspace")
        assert app.highlighted_note.title == "long"
        assert scroll.scroll_y == 3


def test_human_size():
    assert _human_size(0) == "0 B"
    assert _human_size(1023) == "1023 B"
    assert _human_size(2048) == "2.0 KB"
    assert _human_size(5 * 1024 * 1024) == "5.0 MB"
    # Values that round to 1024.0 in the smaller unit roll over instead.
    assert _human_size(1048570) == "1.0 MB"
    assert _human_size(1073741823) == "1.0 GB"
