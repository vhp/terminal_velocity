Terminal Velocity is a fast note-taking app for the UNIX terminal. Start
typing and you're either looking at the note you wanted or about to create
it; hit `enter` and it opens in your editor. It's a terminal take on the OS X
classic [Notational Velocity](http://notational.net/).

Version 2.0 is a ground-up modernization: Python 3.11+, a
[Textual](https://textual.textualize.io/) UI, and in-memory search that stays
quick with thousands of notes. It runs on Linux and macOS.

The 2.0 modernization was carried out with
[Claude Code](https://www.anthropic.com/claude-code).


### Install

You'll need Python 3.11+ and [uv](https://docs.astral.sh/uv/).

    git clone https://github.com/vhp/terminal_velocity.git
    cd terminal_velocity
    make install

That puts `terminal-velocity` on your PATH (plus `terminal_velocity`, kept
around for old muscle memory). Then just run:

    terminal-velocity

Notes live in `~/Notes` unless you point it somewhere else:

    terminal-velocity path/to/your/notes/dir

To quit, press `ctrl-x` or `ctrl-q`. `escape` works too: it clears the
highlight, then the search box, then quits. `ctrl-c` won't quit; it just
reminds you about `ctrl-x`.


### Create Notes

Type a title and hit `enter`, and the new note opens in your editor. As you
type, the list narrows to notes that already match, so you get a chance to
open the related note instead of starting a duplicate.

Put `/` in a title to file the note in a subdirectory, e.g.
`programming/python/How to use decorators in Python`. Missing directories are
created for you.


### Find Notes

Same box, different intent: type a few words from a note's title or body and
the list narrows as you go. Move the highlight with `up`/`down` or
`page up`/`page down`, then hit `enter` to open it. Or just click a note, which
opens it right away.


### Autocomplete

Type the start of a note's title and that note gets highlighted, with the rest
of its title suggested inline. Press `tab` (or `right` at the end of the line)
to accept the suggestion, and `enter` to open the note. An exact title match
wins over longer titles that start the same way. Matching follows the same
smart-case rule as search (see Details).

Want a new note whose title is the start of an existing one, like `meeting`
when `meeting notes` already exists? Hit `escape` to clear the highlight, then
`enter` creates your note.


### Linking Notes

`ctrl-y` copies a link to the highlighted note to your clipboard, ready to
paste into another note. Handy for Zettelkasten-style setups.

What gets copied is up to the `yank_format` setting:

| `yank_format` | Example |
| --- | --- |
| `wiki` (default) | `[[work/standup]]` |
| `markdown` | `[work/standup](work/standup.txt)` |
| `title` | `work/standup` |
| `filename` | `work/standup.txt` |

Paths are relative to the notes directory and copied as-is, so a `markdown`
link to a file with spaces in its name may need a touch-up.

To reach the clipboard, set `copy_command` to your system's clipboard tool
(`wl-copy` on Wayland, `xclip -selection clipboard` on X11, `pbcopy` on macOS)
and the text gets piped to it. Leave it unset and the app sends an OSC 52
escape sequence instead. kitty, WezTerm, Alacritty, Ghostty, and Konsole 24.12+
honor it, and so does iTerm2 once "Applications in terminal may access
clipboard" is on. Terminal.app, GNOME Terminal, and other VTE-based terminals
ignore it, so set `copy_command` there. Inside tmux, OSC 52 also needs
`set -g set-clipboard on`.

Prefer a different key? Set `yank_key` in Textual key syntax, like `ctrl+g` or
`f2`.


### Layouts

Two layouts, picked with the `layout` setting (or `--layout`):

- `list` (the default): the classic single-pane note list.
- `preview`: the filtered list on the left, a scrollable read-only preview of
  the highlighted note on the right, and a stats bar (size, line count,
  modified time, path) along the bottom. `shift`+`up`/`down`/`page up`/`page
  down` scroll the preview, `shift`+`home`/`end` jump to its top or bottom,
  and the mouse wheel works too. Some terminals keep `shift`+`page up`/`page
  down` for their own scrollback; use the other keys there.

Press `ctrl-r` any time to rescan the notes directory.


### Configuration

The notes directory, editor, filename extensions, layout, and linking settings
can all be set with command-line options or in a `~/.tvrc` config file;
command-line options win. For the full list, run:

    terminal-velocity -h


### Syncing

Your notes are just plain text files in a folder, so sync them however you
like: Dropbox, Syncthing, iCloud, git. Keep the notes directory somewhere that
syncs and you're done.


### Details

Notes are plain text files in a notes directory (`~/Notes` by default). They're
read into memory once and searched there, so filtering stays fast even with
thousands of notes. The directory is rescanned when you come back from the
editor or press `ctrl-r`.

The most recently modified notes sit at the top.

Search matches words, not phrases: a note shows up if every word you typed
appears somewhere in its title or body, in any order.

Search is smart-case. An all-lowercase word matches any case; a word with a
capital letter in it has to match exactly.

Subdirectories are searched recursively, but only files whose extension is in
the `extensions` setting count as notes (`.txt`, `.md`, `.markdown`, `.rst`,
and a few other variants by default, plus the extension new notes use). Hidden
files and folders, editor backups ending in `~`, and anything named in
`exclude` (`src`, `backup`, `ignore`, `tmp`, `old` by default) are skipped. New
notes follow the same rules, so a title like `tmp/idea` or `.secret` is
rejected rather than created somewhere the scan would never find it. To give
new notes a different extension, set `extension` (or `--extension`).

Terminal Velocity never opens your notes for writing. All editing happens in
your editor, and the only file it ever creates is a new, empty note. There's no
rename or move yet, but you're free to shuffle files around with other tools;
if you do that while the app is running, press `ctrl-r` so the list catches up.


### Credits

User interaction copied from [Notational Velocity](http://notational.net/).

Some code snippets and ideas borrowed from
[Andrew Wagner](https://github.com/drewm1980/nv-console) and
[Simon Greenhill](https://web.archive.org/web/20200622082824/https://bitbucket.org/simongreenhill/n).

Written in [Python](https://www.python.org/) using
[Textual](https://textual.textualize.io/).
