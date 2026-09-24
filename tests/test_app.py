"""Textual pilot tests for the TerminalVelocityApp UI flows."""

import contextlib

import pytest
from helpers import make_app

from terminal_velocity.preview import PreviewApp


async def test_typing_filters_note_list(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        assert len(app.matches) == 3
        await pilot.press(*"banana")
        assert [n.title for n in app.matches] == ["banana"]


async def test_tab_completes_to_true_title_case(notes_dir):
    # A lowercase query matches a capitalized title case-insensitively; Tab
    # must complete the search box to the note's real casing.
    (notes_dir / "Zebra Notes.txt").write_text("stripes")
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"zebra")
        await pilot.press("tab")
        assert app.query_one("Input").value == "Zebra Notes"


async def test_editor_edit_is_picked_up_and_reselected(notes_dir, monkeypatch):
    # Exercise the real suspend -> subprocess -> rescan -> reselect branch.
    # suspend is patched to a no-op because the headless driver cannot
    # suspend; the editor command actually appends to the note file.
    app = make_app(notes_dir, editor="sh -c 'printf added >> \"$1\"' _")
    monkeypatch.setattr(app, "suspend", lambda: contextlib.nullcontext())
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        assert app.highlighted_note.title == "banana"
        await pilot.press("enter")
        await pilot.pause()
        assert "added" in app.notebook.get_by_title("banana").contents
        assert app.highlighted_note.title == "banana"


async def test_prefix_query_highlights_match_and_down_moves(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"apple")
        # Both apple notes match; the most recent prefix match is highlighted.
        assert app.highlighted_note is not None
        assert app.highlighted_note.title == "applesauce"
        start = [n.title for n in app.matches].index("applesauce")
        await pilot.press("down")
        assert app.highlighted_note.title == app.matches[min(start + 1, len(app.matches) - 1)].title


async def test_escape_clears_then_quits(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"apple")
        assert app.highlighted_note is not None
        await pilot.press("escape")
        assert app.highlighted_note is None
        await pilot.press("escape")
        assert app.query_one("Input").value == ""
        await pilot.press("escape")
        assert app.return_value is None and not app.is_running


async def test_enter_on_unmatched_query_creates_note(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"brand new note")
        assert app.matches == []
        await pilot.press("enter")
        assert (notes_dir / "brand new note.txt").exists()
        assert app.notebook.get_by_title("brand new note") is not None


async def test_tab_accepts_autocomplete(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"apples")
        await pilot.press("tab")
        assert app.query_one("Input").value == "applesauce"


async def test_uppercase_query_does_not_crash(notes_dir):
    # Regression: "Apple" prefix-matches "apple pie" case-insensitively, but
    # the case-sensitive search excludes it; the highlight logic must not
    # look up a note that is not in the match list.
    (notes_dir / "hardware.txt").write_text("I like Apple laptops")
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"Apple")
        assert app.is_running
        assert [n.title for n in app.matches] == ["hardware"]
        assert app.highlighted_note is None


async def test_bracketed_title_renders_literally(notes_dir):
    (notes_dir / "meeting [work].txt").write_text("agenda")
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"agenda")
        assert [n.title for n in app.matches] == ["meeting [work]"]
        from textual.widgets import OptionList

        prompt = app.query_one(OptionList).get_option_at_index(0).prompt
        assert prompt.plain == "meeting [work]"


async def test_malformed_markup_title_does_not_crash(notes_dir):
    # A subdirectory named "x [" gives the title "x [/y", which is invalid
    # Textual markup if parsed.
    sub = notes_dir / "x ["
    sub.mkdir()
    (sub / "y.txt").write_text("weird dir name")
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"weird")
        assert app.is_running
        assert [n.title for n in app.matches] == ["x [/y"]


async def test_enter_on_highlighted_note_keeps_selection(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"apples")
        assert app.highlighted_note.title == "applesauce"
        # Suspend is unsupported headless, so the editor is skipped, but the
        # rescan and keep-selection path still runs.
        await pilot.press("enter")
        assert app.is_running
        assert app.highlighted_note.title == "applesauce"


async def test_overlong_title_notifies_instead_of_crashing(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*("z" * 300))
        await pilot.press("enter")
        assert app.is_running
        assert not any(p.name.startswith("zzz") for p in notes_dir.iterdir())


async def test_trailing_space_query_opens_existing_note(notes_dir):
    (notes_dir / "todo.txt").write_text("things")
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"todo", "space")
        assert app.highlighted_note is None
        await pilot.press("enter")
        assert app.is_running
        assert not (notes_dir / "todo .txt").exists()
        assert app.highlighted_note is not None
        assert app.highlighted_note.title == "todo"


async def test_focus_stays_on_input_after_shift_tab(notes_dir):
    from textual.widgets import Input

    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press("shift+tab")
        assert isinstance(app.focused, Input)


async def test_lookup_falls_back_to_case_insensitive(notes_dir):
    # On case-insensitive filesystems a differently-cased title collides on
    # disk; _lookup must still find the existing note so it opens instead of
    # dead-ending. This exercises the fallback on any filesystem.
    (notes_dir / "Meeting.txt").write_text("agenda")
    app = make_app(notes_dir)
    async with app.run_test():
        app.notebook.scan()
        found = app._lookup("meeting")
        assert found is not None
        assert found.title == "Meeting"


async def test_open_flow_leaves_files_untouched(notes_dir):
    import hashlib

    def digest():
        h = hashlib.sha256()
        for p in sorted(notes_dir.rglob("*")):
            if p.is_file():
                st = p.stat()
                h.update(f"{p}:{st.st_mtime_ns}:{st.st_size}".encode())
                h.update(p.read_bytes())
        return h.hexdigest()

    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        before = digest()
        # Open a highlighted note (editor is skipped headless via SuspendNotSupported).
        await pilot.press(*"banana")
        assert app.highlighted_note.title == "banana"
        await pilot.press("enter")
        # Clear the highlight but keep the text, so Enter takes the add_new path
        # and collides with the existing note.
        await pilot.press("escape")
        assert app.highlighted_note is None
        await pilot.press("enter")
        assert digest() == before


async def test_ctrl_r_picks_up_new_file(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        assert len(app.matches) == 3
        (notes_dir / "cherry.txt").write_text("new fruit out of band")
        await pilot.press("ctrl+r")
        assert "cherry" in [n.title for n in app.matches]


async def test_down_from_no_selection_selects_first(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        # An empty query has no prefix match, so nothing starts highlighted.
        assert app.highlighted_note is None
        await pilot.press("down")
        assert app.highlighted_note is app.matches[0]


async def test_cursor_clamps_at_both_ends(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press("down")
        for _ in range(10):
            await pilot.press("up")
        assert app.query_one("OptionList").highlighted == 0
        for _ in range(10):
            await pilot.press("down")
        assert app.query_one("OptionList").highlighted == len(app.matches) - 1


async def test_empty_notebook_shows_placeholder(tmp_path):
    app = make_app(tmp_path)
    async with app.run_test():
        assert app.matches == []
        placeholder = app.query_one("#empty-placeholder")
        assert placeholder.display is True
        assert "no notes yet" in placeholder.render().plain.lower()


async def test_no_match_shows_create_hint(notes_dir):
    app = make_app(notes_dir)
    async with app.run_test() as pilot:
        await pilot.press(*"zzznope")
        placeholder = app.query_one("#empty-placeholder")
        assert placeholder.display is True
        assert "press enter to create" in placeholder.render().plain.lower()


def _capture_osc52(app, monkeypatch):
    """Record what the app sends to the clipboard via OSC 52."""
    copied = []
    monkeypatch.setattr(app, "copy_to_clipboard", copied.append)
    return copied


def _capture_notify(app, monkeypatch):
    """Record every notification as a (message, severity) pair."""
    notes = []

    def notify(message, *, severity="information", **_):
        notes.append((message, severity))

    monkeypatch.setattr(app, "notify", notify)
    return notes


async def test_yank_without_a_highlight_copies_nothing(notes_dir, monkeypatch):
    app = make_app(notes_dir)
    copied = _capture_osc52(app, monkeypatch)
    notes = _capture_notify(app, monkeypatch)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        await pilot.press("escape")
        assert app.highlighted_note is None
        await pilot.press("ctrl+y")
        assert copied == []
        assert notes == [("No note highlighted to yank", "warning")]


async def test_yank_works_in_the_preview_layout(notes_dir, monkeypatch):
    # PreviewApp redeclares BINDINGS; Textual merges rather than replaces.
    app = make_app(notes_dir, app_cls=PreviewApp)
    copied = _capture_osc52(app, monkeypatch)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        await pilot.press("ctrl+y")
        assert copied == ["[[banana]]"]


async def test_yank_uses_osc52_without_a_copy_command(notes_dir, monkeypatch):
    app = make_app(notes_dir)
    copied = _capture_osc52(app, monkeypatch)
    notes = _capture_notify(app, monkeypatch)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        await pilot.press("ctrl+y")
        assert copied == ["[[banana]]"]
        assert notes == [("Sent [[banana]] to the terminal clipboard", "information")]


async def test_yank_pipes_the_link_to_the_copy_command(notes_dir, tmp_path, monkeypatch):
    out = tmp_path / "clipboard"
    app = make_app(notes_dir, copy_command=f"sh -c 'cat > \"$0\"' {out}")
    copied = _capture_osc52(app, monkeypatch)
    notes = _capture_notify(app, monkeypatch)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        await pilot.press("ctrl+y")
        assert out.read_text() == "[[banana]]"
        assert copied == []
        assert notes == [("Copied [[banana]]", "information")]


@pytest.mark.parametrize(
    ("copy_command", "error"),
    [
        ("false", "exited with status 1"),
        ("no-such-copy-tool-tv", "copy command failed"),
        ("'unterminated", "copy_command setting is invalid"),
    ],
)
async def test_copy_command_failure_reports_an_error(notes_dir, monkeypatch, copy_command, error):
    app = make_app(notes_dir, copy_command=copy_command)
    copied = _capture_osc52(app, monkeypatch)
    notes = _capture_notify(app, monkeypatch)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        await pilot.press("ctrl+y")
        assert copied == []
        assert len(notes) == 1
        message, severity = notes[0]
        assert severity == "error"
        assert error in message


async def test_yank_of_undecodable_filename_does_not_crash(notes_dir, tmp_path, monkeypatch):
    out = tmp_path / "clipboard"
    app = make_app(notes_dir, copy_command=f"sh -c 'cat > \"$0\"' {out}")
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        # How os.walk surfaces a non-UTF-8 byte on Linux; macOS can't create one.
        app.highlighted_note.title = "caf" + b"\xe9".decode("utf-8", "surrogateescape")
        await pilot.press("ctrl+y")
        assert app.is_running
        assert out.read_text(encoding="utf-8") == "[[caf�]]"


async def test_yank_strips_c1_control_rejoined_from_escaped_bytes(notes_dir, monkeypatch):
    app = make_app(notes_dir)
    copied = _capture_osc52(app, monkeypatch)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        # Filename bytes a\xc2\x01\x85b after scan strips \x01; \xc2\x85 is UTF-8 for U+0085.
        app.highlighted_note.title = b"a\xc2\x85b".decode("utf-8", "surrogateescape")
        await pilot.press("ctrl+y")
        assert copied == ["[[ab]]"]


@pytest.mark.parametrize(
    ("yank_format", "expected"),
    [
        ("wiki", "[[work/standup]]"),
        ("markdown", "[work/standup](work/standup.txt)"),
        ("title", "work/standup"),
        ("filename", "work/standup.txt"),
    ],
)
async def test_yank_format_shapes_the_copied_link(notes_dir, monkeypatch, yank_format, expected):
    (notes_dir / "work").mkdir()
    (notes_dir / "work" / "standup.txt").write_text("daily")
    app = make_app(notes_dir, yank_format=yank_format)
    copied = _capture_osc52(app, monkeypatch)
    async with app.run_test() as pilot:
        # "standup" can't prefix-match "work/standup", so arrow down to highlight it.
        await pilot.press(*"standup")
        await pilot.press("down")
        await pilot.press("ctrl+y")
        assert copied == [expected]


async def test_yank_key_is_configurable(notes_dir, monkeypatch):
    app = make_app(notes_dir, yank_key="ctrl+k")
    copied = _capture_osc52(app, monkeypatch)
    async with app.run_test() as pilot:
        await pilot.press(*"banana")
        await pilot.press("ctrl+y")
        assert copied == []
        await pilot.press("ctrl+k")
        assert copied == ["[[banana]]"]
