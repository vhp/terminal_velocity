"""Shared test helpers: app construction for pilot tests."""

from terminal_velocity.app import TerminalVelocityApp
from terminal_velocity.cli import Config
from terminal_velocity.notebook import NoteBook


def make_app(notes_dir, app_cls=TerminalVelocityApp, editor="true"):
    """Build an app of the given class over a fresh NoteBook for notes_dir."""
    config = Config(
        notes_dir=notes_dir,
        editor=editor,
        extension=".txt",
        extensions=[".txt"],
        exclude=[],
        debug=False,
        log_file=notes_dir / "tv.log",
    )
    notebook = NoteBook(notes_dir, extension=".txt", extensions=[".txt"])
    return app_cls(config=config, notebook=notebook)
