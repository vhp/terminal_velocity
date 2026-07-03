"""Textual pilot tests for the TerminalVelocityApp UI flows."""

import contextlib

from helpers import make_app


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
