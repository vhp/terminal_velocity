Terminal Velocity is a fast, cross-platform note-taking application for the
UNIX terminal. It's a clone of the OS X app [Notational
Velocity](http://notational.net/) that runs in a terminal and opens your
notes in your editor. Version 2.0 is a modernized rewrite on Python 3.11+ and
[Textual](https://textual.textualize.io/); it runs on macOS and Linux.

The 2.0 modernization was carried out with
[Claude Code](https://www.anthropic.com/claude-code).


### Install

Terminal Velocity requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

    git clone https://github.com/vhp/terminal_velocity.git
    cd terminal_velocity
    make install

This installs the `terminal-velocity` command (with `terminal_velocity` kept
as a back-compatible alias). Then to launch it just run:

    terminal-velocity

To use a different notes directory, run:

    terminal-velocity path/to/your/notes/dir

To quit the app, press `ctrl-x` or `ctrl-c`.


### Create Notes

To create a new note, type a title for the note and hit `enter`. The note will
be opened in your text editor. As you type the title, the list of notes filters
to show notes that match what you've typed, giving you a chance to open a
related note instead of making a new one.

Titles may contain `/` to create notes in subdirectories.


### Find Notes

The same text area is used for entering the titles of new notes and for
searching notes. To find and open a note, type some words from the note's title
or contents. The list of notes filters as you type to show only matching notes.
When you see the note that you want, use the `up` and `down` arrows to select
it then hit `enter` to open it. You can also use `page up` and `page down` or
mouse clicks to select notes.


### Autocomplete

If you type the beginning of a note's title (case-insensitive), that note will
be automatically selected in the note list and its title will be autocompleted
in the search box. Press `tab` or `right` to accept the completion. Whenever a
note is selected, just hit `enter` to open that note.

If you want to create a new note whose title is a substring of an existing
note's title, then even after you've typed the full title for your new note the
existing note will still be selected by the autocomplete. In this case, hit
`escape` or `ctrl-d` to clear the autocomplete selection, then hit `enter` to
create your note.


### Layouts

Two layouts are available through the `layout` setting (or `--layout`):

- `list` (the default): the classic single-pane note list.
- `preview`: a dual-pane view with the filtered note list on the left, a
  scrollable read-only preview of the selected note on the right, and a stats
  bar (size, line count, modified time, path) along the bottom. In this layout
  `shift`+`up`/`down`/`page up`/`page down` and `shift`+`home`/`end` scroll the
  preview, as does the mouse wheel.

Press `ctrl-r` at any time to rescan the notes directory.


### Configuration

The location of the notes directory, the text editor, the filename extension
for new notes, the layout, etc. can be configured using command-line options
or a `~/.tvrc` config file. For details, run:

    terminal-velocity -h


### Syncing

Since your notes are just a directory of plain text files, it's easy to sync
them using Dropbox, Syncthing, iCloud, git, etc. Just keep your notes directory
inside a synced folder or a git repository.


### Details

Notes are kept as plain text files in a notes directory (`~/Notes` by default).
They are read once into memory and searched there, so filtering stays fast even
with thousands of notes; the notes directory is re-read when you return from
the editor or press `ctrl-r`.

Notes are sorted by modification date, most recently modified at the top.

The search is fuzzy. A note will match a search term if it contains all of the
given search words anywhere in its title or body; the words don't have to
appear consecutively or in the same order.

The search is smart-case. For each search word, if the word is all lower-case
then it will be matched case-insensitively. If the word contains any upper-case
letters then it will be matched case-sensitively.

Subdirectories in your notes directory are searched recursively. To create a
new note in a subdirectory, just give the subdir(s) as part of the note's
title, e.g.: `programming/python/How to use decorators in Python`

You can have note files with different filename extensions. All the files in
your notes directory are searched, regardless of filename extension. To create
a note with a different filename extension use the `--extension` option.

Terminal Velocity never writes to your note files itself: editing is always
done by your editor, and the only file it creates is a new, empty note. It
doesn't support renaming or moving notes yet, but you can move or edit note
files with other tools; that won't interfere with Terminal Velocity as long as
you don't do it while it's running.


### Credits

User interaction copied from [Notational Velocity](http://notational.net/).

Some code snippets and ideas borrowed from
[Andrew Wagner](https://github.com/drewm1980/nv-console) and
[Simon Greenhill](https://bitbucket.org/simongreenhill/n).

Written in [Python](https://www.python.org/) using
[Textual](https://textual.textualize.io/).
