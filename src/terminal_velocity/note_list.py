"""The note list widget: one line per matching note title.

Only the visible rows are rendered, so rebuilding the list on every keystroke
costs the same with fifty notes or fifty thousand. Textual's OptionList
measures every option on each rebuild, which made typing lag in big notebooks.
"""

from rich.segment import Segment
from textual import events
from textual.geometry import Region, Size
from textual.message import Message
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip


class NoteList(ScrollView, can_focus=False):
    """A scrollable list of titles with one highlighted row."""

    COMPONENT_CLASSES = {"note-list--highlighted"}

    DEFAULT_CSS = """
    NoteList {
        overflow-x: hidden;
        & > .note-list--highlighted {
            color: $foreground;
            background: $block-cursor-blurred-background;
        }
    }
    """

    highlighted: reactive[int | None] = reactive(None)

    class Selected(Message):
        """Posted when a title is clicked."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._titles: list[str] = []

    def set_titles(self, titles: list[str]) -> None:
        """Replace the rows and scroll to the top; the highlight is left to the caller."""
        self._titles = titles
        self.virtual_size = Size(self.size.width, len(titles))
        self.scroll_home(animate=False)
        self.refresh()

    def render_line(self, y: int) -> Strip:
        index = self.scroll_offset.y + y
        width = self.size.width
        if index >= len(self._titles):
            return Strip.blank(width, self.rich_style)
        if index == self.highlighted:
            style = self.get_component_rich_style("note-list--highlighted")
        else:
            style = self.rich_style
        return Strip([Segment(self._titles[index], style)]).crop_extend(0, width, style)

    def watch_highlighted(self, highlighted: int | None) -> None:
        if highlighted is not None:
            self.scroll_to_region(Region(0, highlighted, 1, 1), animate=False)
        self.refresh()

    def on_click(self, event: events.Click) -> None:
        offset = event.get_content_offset(self)
        if offset is None:
            return
        index = self.scroll_offset.y + offset.y
        if index < len(self._titles):
            self.highlighted = index
            self.post_message(self.Selected(index))
