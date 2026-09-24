# Terminal Velocity

Terminal Velocity is a fast note-taking app for the UNIX terminal. It lets
you find or create a note as quickly as possible, then opens it in your
configured editor. It is heavily inspired by the OS X app [Notational
Velocity](http://notational.net/).

Version 2.0 is a modernization: Python 3.11+, a
[Textual](https://textual.textualize.io/)-based UI, in-memory search (no
disk reads while typing, fast with thousands of notes), and a data-safety
guarantee: the app never opens your note files for writing. The only write it
ever performs is creating a new, empty note file; all editing happens in your
editor. It runs on macOS and Linux.

The 2.0 modernization was carried out with [Claude Code](https://www.anthropic.com/claude-code).

**If you find a real bug and need help, email me, Vincent. My address is on
my GitHub profile: https://github.com/vhp.**

## Installation

Requires Python 3.11+. Install it with [uv](https://docs.astral.sh/uv/) or
[pipx](https://pipx.pypa.io/), which give the app its own environment and put
the `terminal-velocity` command (and `terminal_velocity`, a
backward-compatible alias) on your PATH:

    uv tool install terminal-velocity

    or

    pipx install terminal-velocity

If the command isn't found afterwards, run `uv tool update-shell` or
`pipx ensurepath` and open a new shell. Upgrade with `uv tool upgrade
terminal-velocity` or `pipx upgrade terminal-velocity`.

`pip install terminal-velocity` also works inside a virtualenv. Outside one,
Homebrew Python and most Linux distros refuse it with an
`externally-managed-environment` error; use uv or pipx instead.

To install the latest code from GitHub rather than a release:

    uv tool install git+https://github.com/vhp/terminal_velocity

    or

    pipx install git+https://github.com/vhp/terminal_velocity

Or install from a clone, where `make install` runs `uv tool install` on
your checkout:

    git clone https://github.com/vhp/terminal_velocity.git
    cd terminal_velocity
    make install

## Usage

    terminal-velocity                        # use ~/Notes (or notes_dir from ~/.tvrc)
    terminal-velocity path/to/your/notes     # use a different notes directory
    terminal-velocity -h                     # list all command-line options

### Keys

- Type to filter notes; the first title match is suggested inline and highlighted.
- `Enter` opens the highlighted note in your editor, or creates a new note titled
  with what you typed. Titles may contain `/` to create notes in subdirectories.
- `Tab`, or `Right` at the end of the text, accepts the inline suggestion.
- `Up`/`Down`/`PgUp`/`PgDn` move the highlight.
- `Esc` clears the highlight, then the search text, then quits.
- `Ctrl-R` rescans the notes directory.
- `Ctrl-Y` copies a link to the highlighted note to the clipboard, ready to
  paste into another note. See [Linking notes](#linking-notes).
- `Ctrl-X` or `Ctrl-C` quits.
- In the preview layout, `Shift-Up`/`Shift-Down`/`Shift-PgUp`/`Shift-PgDn`
  scroll the preview pane and `Shift-Home`/`Shift-End` jump to its top and
  bottom. The mouse wheel scrolls the preview from anywhere except over the
  note list, which scrolls itself. Some terminal emulators reserve
  `Shift-PgUp`/`Shift-PgDn` for their own scrollback; use the other keys or
  the wheel there.

### Linking notes

Zettelkasten-style workflows link notes by pasting one note's name or path
into another. `Ctrl-Y` copies a link to the highlighted note to the system
clipboard; open the other note and paste it as usual (`"+p` in vim).

Set `copy_command` in `~/.tvrc` (or pass `--copy-command`) to the
clipboard tool for your system. `Ctrl-Y` pipes the text to its stdin:

    [DEFAULT]
    # macOS; on Wayland use wl-copy, on X11 xclip -selection clipboard
    copy_command = pbcopy

With no `copy_command`, `Ctrl-Y` emits an OSC 52 escape sequence instead.
Terminals that honor it (kitty, WezTerm, Alacritty, Ghostty, Konsole 24.12
and newer) put the text on the clipboard. iTerm2 does too once "Applications
in terminal may access clipboard" is on under Settings > General >
Selection. Terminal.app, GNOME Terminal, and other VTE-based terminals such
as xfce4-terminal ignore it, so set `copy_command` there. Inside tmux, OSC
52 also needs `set -g set-clipboard on` in `~/.tmux.conf`. The terminal sends
no reply, so the app reports the text as sent, not copied.

Set `yank_format` (or pass `--yank-format`) to choose what gets copied:

| `yank_format` | Example |
| --- | --- |
| `wiki` (default) | `[[work/standup]]` |
| `markdown` | `[work/standup](work/standup.txt)` |
| `title` | `work/standup` |
| `filename` | `work/standup.txt` |

Paths are relative to the notes directory and copied as-is, so a
`markdown` link to a file with spaces in its name may need fixing by hand.

Set `yank_key` (or pass `--yank-key`) to use a different key, in Textual
key syntax such as `ctrl+g` or `f2`. It takes priority over typing in the
search box, so a plain letter would stop you from typing that letter.

### Layouts

Two layouts are available via the `layout` setting (or `--layout`):

- `list` (default): the classic single-pane note list.
- `preview`: a dual-pane view with the filtered list on the left, a
  scrollable read-only preview of the highlighted note on the right, and a
  stats bar (size, line count, modified time) along the bottom.

### Configuration

Options can be set in `~/.tvrc` (INI format); command-line flags override it:

    [DEFAULT]
    editor = vim
    # The filename extension to use for new notes.
    extension = .md
    # The filename extensions to recognize in the notes directory.
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
    make lint     # check lint and formatting with ruff
    make fmt      # auto-format and fix lint issues
    make package  # build the sdist and wheel into dist/
    make clean    # remove the venv, build artifacts, and caches

### Releasing

Uploading needs an owner or maintainer role on the
[terminal-velocity](https://pypi.org/project/terminal-velocity/) PyPI project
and an API token in `UV_PUBLISH_TOKEN`.

1. Bump `version` in `pyproject.toml` and date the entry in `CHANGELOG.txt`.
2. `make package` builds the sdist and wheel into `dist/`. Check the wheel
   with `uv tool install --force dist/*.whl`.
3. `make publish` uploads to PyPI.

To contribute code to Terminal Velocity, see
[CONTRIBUTING](https://github.com/vhp/terminal_velocity/blob/master/CONTRIBUTING.md#contributing-to-terminal-velocity).
