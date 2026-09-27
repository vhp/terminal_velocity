"""Two-pane UI variant: note list on the left, live preview on the right.

Selected with `layout = preview` in ~/.tvrc (or --layout preview). All search,
autocomplete, and editor behavior is inherited from TerminalVelocityApp; this
adds a scrollable read-only preview of the highlighted note and a stats bar.
Shift+Up/Down/PgUp/PgDn scroll the preview while the search box keeps focus.
"""

from datetime import datetime
from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.widgets import OptionList, Static

from terminal_velocity.app import TerminalVelocityApp
from terminal_velocity.notebook import Note, NoteBook, strip_control_chars


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        # Compare the value as it will be displayed, so 1023.96 KB rolls
        # over to 1.0 MB instead of showing as 1024.0 KB.
        display = value if unit == "B" else round(value, 1)
        if display < 1024 or unit == "GB":
            break
        value /= 1024
    return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"


def _display_path(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _stats_line(note: Note) -> str:
    lines = len(note.contents.splitlines())
    modified = datetime.fromtimestamp(note.mtime).strftime("%Y-%m-%d %H:%M")
    # note.title is already sanitized in scan(), but note.path is the raw
    # on-disk path and may carry control bytes from the filename, so the
    # whole line is stripped before it reaches the terminal.
    return strip_control_chars(
        f"{note.title} | {_human_size(note.size)} | {lines} line{'s' if lines != 1 else ''} "
        f"| modified {modified} | {_display_path(note.path)}"
    )


class PreviewApp(TerminalVelocityApp):
    """The dual-pane layout: search box, list and preview panes, stats bar."""

    CSS = (
        TerminalVelocityApp.CSS
        + """
    #panes {
        height: 1fr;
    }
    #left-pane {
        width: 2fr;
    }
    #preview-scroll {
        width: 3fr;
        border-left: solid $border;
        padding: 0 1;
    }
    #stats-bar {
        height: 1;
        width: 100%;
        background: $surface-lighten-1;
        color: $text;
        padding: 0 1;
    }
    """
    )

    BINDINGS = [
        Binding("shift+up", "scroll_preview(-1)", show=False),
        Binding("shift+down", "scroll_preview(1)", show=False),
        Binding("shift+pageup", "scroll_preview(-10)", show=False),
        Binding("shift+pagedown", "scroll_preview(10)", show=False),
        # Priority: Input binds shift+home/end for text selection, which the
        # preview jump deliberately overrides in this layout.
        Binding("shift+home", "preview_edge('home')", show=False, priority=True),
        Binding("shift+end", "preview_edge('end')", show=False, priority=True),
    ]

    def __init__(self, config, notebook: NoteBook) -> None:
        super().__init__(config, notebook)
        self._refiltering = False
        self._shown: tuple[Path, float] | None = None

    def compose(self) -> ComposeResult:
        """Arrange the shared widgets into panes, plus preview and stats."""
        yield self.search_input()
        with Horizontal(id="panes"):
            with Vertical(id="left-pane"):
                yield self.note_list()
                yield self.empty_placeholder()
            with VerticalScroll(id="preview-scroll"):
                yield Static("", id="preview")
        yield Static("", id="stats-bar")

    def on_mount(self) -> None:
        super().on_mount()
        # Not focusable: the mouse wheel and the shift-key bindings scroll it
        # without focus, and the search box must keep receiving keystrokes.
        self.query_one("#preview-scroll", VerticalScroll).can_focus = False
        self.watch(
            self.query_one(OptionList), "highlighted", self._on_highlight_changed, init=False
        )

    def refilter(self, query, keep=None) -> None:
        # Coalesce: clear_options bounces highlighted through None on every
        # list rebuild, so watcher syncs are suppressed here and one sync
        # runs at the end. This keeps the unchanged-note guard effective
        # (no blank/repaint flicker or scroll reset while typing).
        self._refiltering = True
        try:
            super().refilter(query, keep)
        finally:
            self._refiltering = False
        self._sync_preview()

    def _on_highlight_changed(self) -> None:
        if not self._refiltering:
            self._sync_preview()

    def _sync_preview(self) -> None:
        """Show the highlighted note's contents and stats, or clear both.

        No-op when the same note version is already shown, preserving the
        reader's scroll position while they type.
        """
        note = self.highlighted_note
        shown = (note.path, note.mtime) if note else None
        if shown == self._shown:
            return
        self._shown = shown
        preview = self.query_one("#preview", Static)
        stats = self.query_one("#stats-bar", Static)
        if note is None:
            preview.update("")
            stats.update("")
            return
        preview.update(Content(strip_control_chars(note.contents, keep_newlines=True)))
        stats.update(Content(_stats_line(note)))
        self.query_one("#preview-scroll", VerticalScroll).scroll_home(animate=False)

    def action_refresh(self) -> None:
        # A forced re-read catches content changes that keep the same path and
        # mtime, so reset the preview guard too, or the pane would stay stale.
        self._shown = None
        super().action_refresh()

    def action_scroll_preview(self, lines: int) -> None:
        self.query_one("#preview-scroll", VerticalScroll).scroll_relative(y=lines, animate=False)

    def action_preview_edge(self, edge: str) -> None:
        scroll = self.query_one("#preview-scroll", VerticalScroll)
        if edge == "home":
            scroll.scroll_home(animate=False)
        else:
            scroll.scroll_end(animate=False)

    # Wheel events over scrollable widgets (the list, the preview) are
    # consumed there; anywhere else they bubble up here and scroll the
    # preview, so the wheel works over the search box and stats bar too.
    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self.action_scroll_preview(2)
        event.stop()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self.action_scroll_preview(-2)
        event.stop()
