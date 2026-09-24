"""The Textual user interface: a search box over a filtered note list.

The search input keeps keyboard focus at all times; arrow and page keys move
the highlight in the note list below it. Typing filters the list on every
keystroke against the in-memory notebook. Enter opens the highlighted note
in the configured external editor (the app suspends while it runs), or
creates a new note titled with the query when nothing is highlighted.

Ctrl-Y (the yank_key setting) copies the highlighted note to the clipboard,
shaped by the yank_format setting, so it can be pasted into another note as
a link. The copy goes through the copy_command setting (e.g. pbcopy), or
OSC 52 when that is empty.
"""

import logging
import shlex
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult, SuspendNotSupported
from textual.binding import Binding
from textual.content import Content
from textual.suggester import Suggester
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from terminal_velocity.cli import YANK_FORMATS
from terminal_velocity.notebook import (
    InvalidNoteTitleError,
    NewNoteError,
    Note,
    NoteAlreadyExistsError,
    NoteBook,
    strip_control_chars,
)

logger = logging.getLogger(__name__)


def yank_text(note: Note, root: Path, yank_format: str = "wiki") -> str:
    """The text a yank copies for `note`, rendered with a YANK_FORMATS template.

    Control characters are stripped because titles and paths come raw off
    the disk and get pasted into a terminal editor's buffer. Undecodable
    filename bytes become U+FFFD, since both copy paths need valid UTF-8.
    """
    path = str(note.path.relative_to(root))
    text = YANK_FORMATS[yank_format].format(title=note.title, path=path)
    text = text.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    # Strip after decoding: escaped bytes around a stripped char can rejoin into a C1 control.
    return strip_control_chars(text)


class TitleSuggester(Suggester):
    """Suggests the title of the note the query prefix-matches."""

    def __init__(self, app: "TerminalVelocityApp") -> None:
        # case_sensitive=True keeps the raw query, so the suggestion, the list
        # highlight, and Tab-completion all agree on smart-case matching.
        super().__init__(use_cache=False, case_sensitive=True)
        self._app = app

    async def get_suggestion(self, value: str) -> str | None:
        note = self._app.prefix_match(value)
        return note.title if note else None


class TerminalVelocityApp(App):
    """The note search-and-edit UI: a search box over a live-filtered note list."""

    CSS = """
    Input {
        background: $surface-lighten-1;
        border: round $border;
    }
    OptionList {
        height: 1fr;
        border: none;
        padding: 0 1;
        background: transparent;
    }
    #empty-placeholder {
        height: 1fr;
        content-align: center middle;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "clear_or_quit", "Clear/Quit", priority=True),
        Binding("ctrl+d", "clear_or_quit", show=False, priority=True),
        Binding("ctrl+x", "quit", "Quit", priority=True),
        Binding("ctrl+r", "refresh", "Refresh", priority=True),
        # Priority: the search Input has focus at all times and would
        # otherwise swallow the keystroke as text.
        Binding("ctrl+y", "yank", "Yank", priority=True, id="yank"),
        Binding("tab", "complete", show=False, priority=True),
        Binding("down", "cursor(1)", show=False),
        Binding("up", "cursor(-1)", show=False),
        Binding("pagedown", "cursor(10)", show=False),
        Binding("pageup", "cursor(-10)", show=False),
    ]

    def __init__(self, config, notebook: NoteBook) -> None:
        super().__init__()
        self.config = config
        self.notebook = notebook
        self.matches: list[Note] = []
        self.set_keymap({"yank": config.yank_key})

    def compose(self) -> ComposeResult:
        """Lay out the search box, note list, and empty-state placeholder."""
        yield self.search_input()
        yield self.note_list()
        yield self.empty_placeholder()

    # Widget construction is factored out so layout subclasses rearrange the
    # same widgets instead of re-declaring them.
    def search_input(self) -> Input:
        return Input(placeholder="Find or Create", suggester=TitleSuggester(self))

    def note_list(self) -> OptionList:
        return OptionList(id="note-list")

    def empty_placeholder(self) -> Static:
        return Static("", id="empty-placeholder")

    def on_mount(self) -> None:
        """Focus the search box and show all notes on startup."""
        self.query_one(OptionList).can_focus = False
        self.query_one(Input).focus()
        self.refilter("")

    @property
    def highlighted_note(self) -> Note | None:
        highlighted = self.query_one(OptionList).highlighted
        if highlighted is None or highlighted >= len(self.matches):
            return None
        return self.matches[highlighted]

    def prefix_match(self, query: str, matches: list[Note] | None = None) -> Note | None:
        """The best search match whose title starts with `query`.

        Selecting from the search matches (not the whole notebook) keeps the
        suggestion, the highlight, and the visible list consistent for
        case-sensitive queries.
        """
        if not query:
            return None
        if matches is None:
            matches = self.notebook.search(query)
        query_lower = query.lower()
        return next((n for n in matches if n.title_lower.startswith(query_lower)), None)

    def refilter(self, query: str, keep: Path | None = None) -> None:
        """Rebuild the note list for `query`, highlighting the prefix match.

        If `keep` is given, highlight that note instead (used to restore the
        selection after returning from the editor).
        """
        self.matches = self.notebook.search(query)

        option_list = self.query_one(OptionList)
        option_list.clear_options()
        option_list.add_options([Option(Content(note.title)) for note in self.matches])

        placeholder = self.query_one("#empty-placeholder", Static)
        if self.matches:
            placeholder.display = False
            option_list.display = True
        else:
            placeholder.update(
                "You have no notes yet, to create a note type a note title then press Enter"
                if len(self.notebook) == 0
                else "No matching notes, press Enter to create a new note"
            )
            placeholder.display = True
            option_list.display = False
            return

        highlight: int | None = None
        if keep is not None:
            highlight = next((i for i, note in enumerate(self.matches) if note.path == keep), None)
        if highlight is None:
            prefix_note = self.prefix_match(query, self.matches)
            if prefix_note is not None:
                highlight = self.matches.index(prefix_note)
        option_list.highlighted = highlight

    def open_in_editor(self, path: Path) -> None:
        """Suspend the app to edit `path`, then rescan and reselect that note."""
        try:
            editor_argv = shlex.split(self.config.editor)
        except ValueError as e:
            self.notify(f"Bad editor setting: {e}", severity="error", markup=False)
            return
        if not editor_argv:
            self.notify("No editor configured", severity="error")
            return
        command = [*editor_argv, str(path)]
        try:
            with self.suspend():
                subprocess.call(command)
        except SuspendNotSupported:
            logger.error("Cannot suspend to run editor in this environment")
            self.notify("Cannot suspend to run the editor here", severity="error")
        except OSError as e:
            logger.error("Could not run editor %r: %s", command, e)
            self.notify(f"Could not run editor: {e}", severity="error", markup=False)

        self.notebook.scan()
        self.refilter(self.query_one(Input).value, keep=path)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-filter the note list as the search text changes."""
        self.refilter(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Open the highlighted note, or create/open one from the typed title."""
        note = self.highlighted_note
        if note is not None:
            self.open_in_editor(note.path)
            return
        title = self.notebook.normalize_title(event.value)
        if not title:
            return
        try:
            new_note = self.notebook.add_new(title)
            self.open_in_editor(new_note.path)
        except NoteAlreadyExistsError:
            existing = self._find_existing(title)
            if existing is not None:
                self.open_in_editor(existing.path)
            else:
                self.notify(f"Could not open note: {title}", severity="error", markup=False)
        except InvalidNoteTitleError:
            self.notify(f"Invalid note title: {title!r}", severity="error", markup=False)
        except NewNoteError as e:
            self.notify(str(e), severity="error", markup=False)

    def _find_existing(self, title: str) -> Note | None:
        """Locate the note that made add_new raise NoteAlreadyExistsError."""
        existing = self._lookup(title)
        if existing is None:
            # The file exists on disk but not in memory (created out of band).
            self.notebook.scan()
            existing = self._lookup(title)
        return existing

    def _lookup(self, title: str) -> Note | None:
        """Find a note by title, falling back to a case-insensitive match.

        The case-insensitive pass handles case-insensitive filesystems (e.g.
        macOS APFS), where a differently-cased title collides on disk.
        """
        exact = self.notebook.get_by_title(
            title, self.notebook.extension
        ) or self.notebook.get_by_title(title)
        if exact is not None:
            return exact
        lowered = title.lower()
        return next((note for note in self.notebook if note.title.lower() == lowered), None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Open the note the user clicked."""
        if event.option_index < len(self.matches):
            self.open_in_editor(self.matches[event.option_index].path)

    def action_cursor(self, delta: int) -> None:
        """Move the list highlight by `delta`, selecting the first note if none is."""
        if not self.matches:
            return
        option_list = self.query_one(OptionList)
        if option_list.highlighted is None:
            option_list.highlighted = 0 if delta > 0 else len(self.matches) - 1
        else:
            option_list.highlighted = max(
                0, min(len(self.matches) - 1, option_list.highlighted + delta)
            )

    def action_complete(self) -> None:
        """Accept the autocomplete suggestion, turning it into typed text."""
        search_box = self.query_one(Input)
        note = self.prefix_match(search_box.value)
        if note is not None and len(note.title) > len(search_box.value):
            search_box.value = note.title
            search_box.cursor_position = len(note.title)

    def action_yank(self) -> None:
        """Copy the highlighted note to the clipboard in the yank_format shape."""
        note = self.highlighted_note
        if note is None:
            self.notify("No note highlighted to yank", severity="warning")
            return
        text = yank_text(note, self.notebook.path, self.config.yank_format)
        if not self.config.copy_command:
            # OSC 52 gives no reply, so this can't claim the copy landed.
            self.copy_to_clipboard(text)
            self.notify(f"Sent {text} to the terminal clipboard", markup=False)
            return
        error = self.run_copy_command(text)
        if error:
            self.notify(f"Could not copy {text}: {error}", severity="error", markup=False)
            return
        self.notify(f"Copied {text}", markup=False)

    def run_copy_command(self, text: str) -> str | None:
        """Pipe `text` to the copy_command setting; return what went wrong, if anything."""
        try:
            argv = shlex.split(self.config.copy_command)
        except ValueError as e:
            return f"the copy_command setting is invalid: {e}"
        if not argv:
            return "the copy_command setting is empty"
        # Blocks the event loop: fine for pbcopy/xclip/wl-copy, a hung command freezes the UI 5s.
        try:
            # DEVNULL, not pipes: xclip's forked child holds pipes open until the timeout.
            result = subprocess.run(
                argv,
                input=text,
                encoding="utf-8",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.error("Could not run copy command %r: %s", argv, e)
            return f"the copy command failed: {e}"
        if result.returncode != 0:
            logger.error("Copy command %r exited with %d", argv, result.returncode)
            return f"the copy command exited with status {result.returncode}"
        return None

    def action_clear_or_quit(self) -> None:
        """Clear the highlight, then the search text, then quit."""
        option_list = self.query_one(OptionList)
        search_box = self.query_one(Input)
        if option_list.highlighted is not None:
            option_list.highlighted = None
        elif search_box.value:
            search_box.value = ""
        else:
            self.exit()

    def action_refresh(self) -> None:
        """Force a full re-read of the notes directory and re-filter."""
        self.notebook.scan(force=True)
        self.refilter(self.query_one(Input).value)
