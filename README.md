# Terminal Velocity

Terminal Velocity is a fast note-taking app for the UNIX terminal, that
focuses on letting you create or find a note as quickly and easily as
possible, then uses your configured editor to open and edit the note. It is
heavily inspired by the OS X app [Notational
Velocity](http://notational.net/).

Version 2.0 is a modernization: Python 3.11+, a
[Textual](https://textual.textualize.io/)-based UI, in-memory search (no
disk reads while typing, fast with thousands of notes), and a data-safety
guarantee: the app never opens your note files for writing - the only write
it ever performs is creating a new, empty note file. Editing is always done
by your editor. It runs on macOS and Linux.

The 2.0 modernization was carried out with [Claude Code](https://www.anthropic.com/claude-code).

**If you find a true bug and need help then please reach out via email to Vincent.
You can find my email in my profile https://github.com/vhp.**

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

    git clone https://github.com/vhp/terminal_velocity.git
    cd terminal_velocity
    make install

This installs the `terminal-velocity` command (and `terminal_velocity` as a
back-compat alias) via `uv tool install`.

## Usage

    terminal-velocity                        # uses ~/Notes (or notes_dir from ~/.tvrc)
    terminal-velocity path/to/your/notes     # use a different notes directory
    terminal-velocity -h                     # all command-line options

### Keys

- Type to filter notes; the first title match is suggested inline and highlighted.
- `Enter` opens the highlighted note in your editor, or creates a new note titled
  with what you typed. Titles may contain `/` to create notes in subdirectories.
- `Tab` or `Right` (at end of text) accepts the inline suggestion.
- `Up`/`Down`/`PgUp`/`PgDn` move the highlight.
- `Esc` clears the highlight, then the search text, then quits.
- `Ctrl-R` rescans the notes directory.
- `Ctrl-X` or `Ctrl-C` quits.
- In the preview layout, `Shift-Up`/`Shift-Down`/`Shift-PgUp`/`Shift-PgDn`
  scroll the preview pane and `Shift-Home`/`Shift-End` jump to its top and
  bottom. The mouse wheel scrolls the preview from anywhere except over the
  note list, which scrolls itself. Some terminal emulators reserve
  `Shift-PgUp`/`Shift-PgDn` for their own scrollback; use the other keys or
  the wheel there.

### Layouts

Two layouts are available via the `layout` setting (or `--layout`):

- `list` (default): the classic single-pane note list.
- `preview`: a dual-pane view; the filtered list sits on the left, a
  scrollable read-only preview of the highlighted note on the right, and a
  stats bar (size, line count, modified time) along the bottom.

### Configuration

Options can be set in `~/.tvrc` (INI format); command-line flags override it:

    [DEFAULT]
    editor = vim
    # The filename extension to use for new notes.
    extension = .md
    # The filename extensions to recognize in the notes dir.
    extensions = .txt, .md, .markdown, .rst
    notes_dir = ~/Notes
    # UI layout: list (default) or preview (dual-pane with preview and stats).
    layout = preview

The editor is chosen in this order: the `-e` flag, the `editor` setting in
`~/.tvrc`, the `EDITOR` environment variable, then `vim`.

## Development

    make dev      # create the venv and install dependencies (uv sync)
    make run      # run the app (make run ARGS="path/to/notes")
    make test     # run the test suite
    make lint     # ruff check + format check
    make fmt      # auto-format and fix lint issues
    make package  # build the sdist and wheel into dist/
    make clean    # remove the venv, build artifacts, and caches

### Releasing

`make package` builds the source distribution and wheel into `dist/`. Upload
them to PyPI with `uv publish` (or `twine upload dist/*`).

To contribute code to Terminal Velocity, see
[CONTRIBUTING](https://github.com/vhp/terminal_velocity/blob/master/CONTRIBUTING.md#contributing-to-terminal-velocity).
